import argparse
import time

import numpy as np
import sys
import torch
import torch.utils.data
import torch.nn as nn

import torch.optim as optim


sys.path.append('/home/wanggang/projects/GeneInference/dense/')
from model.x1_x2_2 import x1_x2_2
from model.x1_x2_3 import x1_x2_3
from utils.load_data import MyDataSet
from model.e2 import e2
from model.e2_1 import e2_1
from model.e2_2 import e2_2
from model.e3 import e3
from model.x2_x3_2 import x2_x3_2
from model.x2_x3_3 import x2_x3_3
from model.relu_1 import relu_1
from model.relu_2 import relu_2
from model.relu_3 import relu_3
from model.p_relu_1 import p_relu_1
from model.p_relu_2 import p_relu_2
from model.p_relu_3 import p_relu_3
from model.df_relu_2 import df_relu_2
from model.df_relu_3 import df_relu_3
from model.relu_bn_3 import relu_bn_3
from model.x1_x2_2_e import x1_x2_2_e
from model.x1_x2_3_e import x1_x2_3_e
'''
1、定义超参数
'''
# 采用的网络模型
MODEL = 'relu_1'
# 训练批次数
NUM_EPOCH = 1000
# batch的大小
BATCH_SIZE = 500
# 输入维度大小
IN_SIZE = 943
# 输出维度大小
OUT_SIZE = 4760
# 隐藏层单元数
HIDDEN_SIZE = 1000
# dropout
DROPOUT_RATE = 0.1
# 学习率
LEARNING_RATE = 5e-4
# 数据集
DATASET = "0-4760"
# 试验次数的序号
FILENUM = 0

def get_arguments():
    """
    Parse all the arguments provided from the CLI.

    Returns:
          A list of parsed arguments.
    """
    parser = argparse.ArgumentParser(description="dense idea's arguments")
    parser.add_argument("--model", type=str, default=MODEL,
                        help="the network structure that you want use")
    parser.add_argument("--num-epoch", type=int, default=NUM_EPOCH,
                        help="iter numbers")
    parser.add_argument("--batch-size", type=int, default=BATCH_SIZE,
                        help="batch's size")
    parser.add_argument("--in-size", type=int, default=IN_SIZE,
                        help="input size, 943?")
    parser.add_argument("--out-size", type=int, default=OUT_SIZE,
                        help="output size, 9520,4760,or 3173?")
    parser.add_argument("--hidden-size", type=int, default=HIDDEN_SIZE,
                        help="hidden layer's size")
    parser.add_argument("--dropout-rate", type=float, default=DROPOUT_RATE,
                        help="dropout rate, 0.1,0.25?")
    parser.add_argument("--learning-rate", type=float, default=LEARNING_RATE,
                        help="learning rate, 5e-4?")
    parser.add_argument("--dataset", type=str, default=DATASET,
                        help="0-4760 or 4760-9520")
    parser.add_argument("--file-num", type=int, default=FILENUM,
                        help="the number of test times")
    return parser.parse_args()

args = get_arguments()


def main():
    '''
    2、读取数据
    '''
    print('loading data...')

    tr_set = MyDataSet(x_path='../../third_dataset/GTEx_X_tr_float64.npy', y_path='../../third_dataset/GTEx_Y_tr_'+str(args.dataset)+'_float64.npy')
    tr_loader = torch.utils.data.DataLoader(tr_set, batch_size=args.batch_size, shuffle=True)

    X_va = torch.from_numpy(np.array(np.load('../../third_dataset/GTEx_X_va_float64.npy'))).type(torch.FloatTensor).cuda()
    Y_va = torch.from_numpy(np.array(np.load('../../third_dataset/GTEx_Y_va_'+str(args.dataset)+'_float64.npy'))).type(torch.FloatTensor).cuda()

    X_te = torch.from_numpy(np.array(np.load('../../third_dataset/GTEx_X_te_float64.npy'))).type(torch.FloatTensor).cuda()
    Y_te = torch.from_numpy(np.array(np.load('../../third_dataset/GTEx_Y_te_' + str(args.dataset) + '_float64.npy'))).type(torch.FloatTensor).cuda()
    '''
    2、定义网络
    '''
    net = globals()[args.model](args.in_size, args.hidden_size, args.out_size, args.dropout_rate).cuda()
    net = nn.DataParallel(net, device_ids=[0])
    '''
    3、定义Loss和优化器
    '''

    criterion = nn.MSELoss(reduce=True, size_average=False)
    optimizer = optim.Adam(net.module.parameters(), lr=args.learning_rate)
    '''
    4、开始训练网络
    '''
    MAE_va_best = 10.0
    net_parameters = {}
    best_te_res = torch.zeros(400, 4760)

    outlog = open('../../res/dense/'+args.model+'-'+str(args.hidden_size)+'-' + str(args.dropout_rate) +'-'+ str(args.dataset) +'-'+str(args.file_num)+'.log', 'w')
    log_str = '\t'.join(map(str, ['epoch', 'MAE_te',  'MAE_tr',  'time(sec)']))
    print(log_str)
    outlog.write(log_str + '\n')
    sys.stdout.flush()

    for epoch in range(args.num_epoch):
        for i, data in enumerate(tr_loader, 0):
            t_old = time.time()
            '''
            开始训练了
            '''
            # forward
            net.train()
            x_batch, y_batch = data
            x_batch = x_batch.type(torch.FloatTensor).cuda()
            y_batch = y_batch.type(torch.FloatTensor).cuda()

            tr_outputs = net.module(x_batch)

            l1_loss = 0
            for param in net.parameters():
                if len(param.shape) == 2:
                    l1_loss += torch.sum(abs(param))

            loss = criterion(tr_outputs, y_batch) + l1_loss
            # backward
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()

            torch.cuda.empty_cache()

            '''
            开始验证了
            '''
            with torch.no_grad():
                net.eval()
                #计算output
                va_outputs = net(X_va)

                #计算MAE
                MAE_tr = np.abs(y_batch.detach().cpu().numpy()  - tr_outputs.detach().cpu().numpy() ).mean()
                MAE_va = np.abs(Y_va.detach().cpu().numpy()  - va_outputs.detach().cpu().numpy() ).mean()

                t_new = time.time()
                log_str = '\t'.join(
                    # 这里18的前提是：88807/5000！！！，但只是序号而已，不重要
                    map(str, [(epoch * 5) + i + 1, '%.6f' % MAE_va,
                              '%.6f' % MAE_tr, int(t_new - t_old)]))
                print(log_str)
                outlog.write(log_str + '\n')
                sys.stdout.flush()
                # 保留最优MAE_te
                if MAE_va < MAE_va_best:
                    MAE_va_best = MAE_va
                    net_parameters = net.state_dict()

                    best_te_res = net(X_te)
                    MAE_te = np.abs(Y_te.detach().cpu().numpy() - best_te_res.detach().cpu().numpy()).mean()
                    MSE_te = np.square(Y_te.detach().cpu().numpy() - best_te_res.detach().cpu().numpy()).mean()

        print("epoch %d training over" % epoch)
    # 保存训练出来的模型
    torch.save(net_parameters, '../../res/dense/' + args.model + '-' + str(
        args.hidden_size) + '-' + str(args.dropout_rate) + '-' + str(args.dataset) + '-' + str(
        args.file_num) + '.pt')
    print("MAE_te:",MAE_te)
    print("MSe_te:",MSE_te)
    np_best_te_res = best_te_res.detach().cpu().numpy()
    np.save('../../res/dense/' + args.model + '-' + str(args.hidden_size) + '-' + str(args.dropout_rate) + '-'
            + str(args.dataset) + '-' + str(args.file_num) + '.npy', np_best_te_res)
    print('MAE_va_best : %.6f' % (MAE_va_best))
    outlog.write('MAE_va_best : %.6f' % (MAE_va_best) + '\n')
    outlog.close()
    print('Finish Training')
main()