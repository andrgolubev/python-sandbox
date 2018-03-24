from __future__ import print_function
import argparse
import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim
from torchvision import datasets, transforms
from torch.autograd import Variable
from utils.flops_benchmark import add_flops_counting_methods


# Training settings
parser = argparse.ArgumentParser(description='PyTorch MNIST Example')
parser.add_argument('--batch-size', type=int, default=64, metavar='N',
                    help='input batch size for training (default: 64)')
parser.add_argument('--test-batch-size', type=int, default=1000, metavar='N',
                    help='input batch size for testing (default: 1000)')
parser.add_argument('--epochs', type=int, default=10, metavar='N',
                    help='number of epochs to train (default: 10)')
parser.add_argument('--lr', type=float, default=0.01, metavar='LR',
                    help='learning rate (default: 0.01)')
parser.add_argument('--momentum', type=float, default=0.5, metavar='M',
                    help='SGD momentum (default: 0.5)')
parser.add_argument('--no-cuda', action='store_true', default=False,
                    help='disables CUDA training')
parser.add_argument('--seed', type=int, default=1, metavar='S',
                    help='random seed (default: 1)')
parser.add_argument('--log-interval', type=int, default=10, metavar='N',
                    help='how many batches to wait before logging training status')
args = parser.parse_args()
args.cuda = not args.no_cuda and torch.cuda.is_available()

torch.manual_seed(args.seed)
if args.cuda:
    torch.cuda.manual_seed(args.seed)


kwargs = {'num_workers': 1, 'pin_memory': True} if args.cuda else {}
train_loader = torch.utils.data.DataLoader(
    datasets.MNIST('../data', train=True, download=True,
                   transform=transforms.Compose([
                       transforms.ToTensor(),
                       transforms.Normalize((0.1307,), (0.3081,))
                   ])),
    batch_size=args.batch_size, shuffle=True, **kwargs)
test_loader = torch.utils.data.DataLoader(
    datasets.MNIST('../data', train=False, transform=transforms.Compose([
                       transforms.ToTensor(),
                       transforms.Normalize((0.1307,), (0.3081,))
                   ])),
    batch_size=args.test_batch_size, shuffle=True, **kwargs)


class Net(nn.Module):
    def __init__(self, conv1_out_size):  # fwd_pass_clb, init_clb):
        super(Net, self).__init__()
        # self._fwd_pass_clb = fwd_pass_clb
        # init_clb(self)
        self.conv1 = nn.Conv2d(1, conv1_out_size, kernel_size=5)
        self.conv2 = nn.Conv2d(conv1_out_size, 20, kernel_size=5)
        self.conv2_drop = nn.Dropout2d()
        self.fc1 = nn.Linear(320, 50)
        self.fc2 = nn.Linear(50, 10)

    def forward(self, x):
        # return self._fwd_pass_clb(self, x)
        x = F.relu(F.max_pool2d(self.conv1(x), 2))
        x = F.relu(F.max_pool2d(self.conv2_drop(self.conv2(x)), 2))
        x = x.view(-1, 320)
        x = F.relu(self.fc1(x))
        x = F.dropout(x, training=self.training)
        x = self.fc2(x)
        return F.log_softmax(x, dim=1)


def train(model, optimizer, epoch):
    model.train()
    for batch_idx, (data, target) in enumerate(train_loader):
        if args.cuda:
            data, target = data.cuda(), target.cuda()
        data, target = Variable(data), Variable(target)
        optimizer.zero_grad()
        output = model(data)
        loss = F.nll_loss(output, target)
        loss.backward()
        optimizer.step()
        # if batch_idx % args.log_interval == 0:
        #     print('Train Epoch: {} [{}/{} ({:.0f}%)]\tLoss: {:.6f}'.format(
        #         epoch, batch_idx * len(data), len(train_loader.dataset),
        #         100. * batch_idx / len(train_loader), loss.data[0]))


def test(model):
    model.eval()
    test_loss = 0
    correct = 0
    for data, target in test_loader:
        if args.cuda:
            data, target = data.cuda(), target.cuda()
        data, target = Variable(data, volatile=True), Variable(target)
        output = model(data)
        test_loss += F.nll_loss(output, target, size_average=False).data[0] # sum up batch loss
        pred = output.data.max(1, keepdim=True)[1] # get the index of the max log-probability
        correct += pred.eq(target.data.view_as(pred)).long().cpu().sum()

    test_loss /= len(test_loader.dataset)
    print('Test set: Average loss: {:.4f}, Accuracy: {}/{} ({:.0f}%)'.format(
        test_loss, correct, len(test_loader.dataset),
        100. * correct / len(test_loader.dataset)))



def full_iteration(conv1_out_size):  # forward_pass_callback, desc, init_clb):
    # model = Net(forward_pass_callback, init_clb)
    model = Net(conv1_out_size)
    optimizer = optim.SGD(model.parameters(), lr=args.lr, momentum=args.momentum)
    model = add_flops_counting_methods(model)
    if args.cuda:
        model.cuda()

    for epoch in range(1, args.epochs + 1):
        train(model, optimizer, epoch)
        pass

    # consider flops counting on test forward pass
    model.start_flops_count()
    print('-'*100)
    test(model)
    print('FLOPS:', model.compute_average_flops_cost(), '| GFLOPS:', model.compute_average_flops_cost() / 1e9)
    print('Model:', model)
    # print('Architecture:', desc)



########################################################################################################################
def main():
    # def parameters1():
    #     def arch(model, x):
    #         x = F.relu(F.max_pool2d(model.conv1(x), 2))
    #         x = F.relu(F.max_pool2d(model.conv2_drop(model.conv2(x)), 2))
    #         x = x.view(-1, 320) # is this a reduction of some kind?
    #         x = F.relu(model.fc1(x))
    #         x = F.dropout(x, training=model.training) # applying dropout ?
    #         x = model.fc2(x)
    #         return F.log_softmax(x, dim=1)
    #     desc = "conv -> pool -> act -> conv -> conv_drop -> pool -> act -> ? -> fc -> act -> dropout? -> fc -> softmax"

    #     def init(model):
    #         model.conv1 = nn.Conv2d(1, 10, kernel_size=5)
    #         model.conv2 = nn.Conv2d(10, 20, kernel_size=5)
    #         model.conv2_drop = nn.Dropout2d()
    #         model.fc1 = nn.Linear(320, 50)
    #         model.fc2 = nn.Linear(50, 10)

    #     return arch, desc, init

    # def parameters2():
    #     def arch(model, x):
    #         x = F.relu(F.max_pool2d(model.conv1(x), 2))
    #         x = F.relu(F.max_pool2d(model.conv2_drop(model.conv2(x)), 2))
    #         x = x.view(-1, 160) # is this a reduction of some kind?
    #         x = F.relu(model.fc1(x))
    #         x = F.dropout(x, training=model.training) # applying dropout ?
    #         x = model.fc2(x)
    #         return F.log_softmax(x, dim=1)
    #     desc = "conv -> pool -> act -> conv -> conv_drop -> pool -> act -> ? -> fc -> act -> dropout? -> fc -> softmax"

    #     def init(model):
    #         model.conv1 = nn.Conv2d(1, 5, kernel_size=5)
    #         model.conv2 = nn.Conv2d(5, 20, kernel_size=5)
    #         model.conv2_drop = nn.Dropout2d()
    #         model.fc1 = nn.Linear(160, 50)
    #         model.fc2 = nn.Linear(50, 10)

    #     return arch, desc, init

    # forward_pass_metadata = [
    #     parameters1(),
    #     parameters2()
    # ]

    # for fwd_callback, desc, init in forward_pass_metadata:
        # full_iteration(fwd_callback, desc, init)
    for out_size in [1, 3, 5, 10, 15]:
        full_iteration(out_size)

main()
