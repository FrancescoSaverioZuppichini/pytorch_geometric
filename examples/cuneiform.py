from __future__ import division, print_function

import os
import sys

import torch
from torch import nn
import torch.nn.functional as F
from torch.autograd import Variable
from torchvision.transforms import Compose

sys.path.insert(0, '.')
sys.path.insert(0, '..')

from torch_geometric.datasets import Cuneiform  # noqa
from torch_geometric.transforms import (RandomRotate, RandomScale,
                                        RandomTranslate, CartesianAdj)  # noqa
from torch_geometric.utils import DataLoader  # noqa
from torch_geometric.nn.modules import SplineConv  # noqa
from torch_geometric.nn.functional import batch_average  # noqa

path = os.path.dirname(os.path.realpath(__file__))
path = os.path.join(path, '..', 'data', 'Cuneiform')
train_transform = Compose([
    RandomRotate(0.1),
    RandomScale(1.1),
    RandomTranslate(0.1),
    CartesianAdj(),
])
transform = CartesianAdj()
train_dataset = Cuneiform(path, train=True, transform=transform)
test_dataset = Cuneiform(path, train=False, transform=transform)

batch_size = 32
train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True)
test_loader = DataLoader(test_dataset, batch_size=batch_size, shuffle=True)


class Net(nn.Module):
    def __init__(self):
        super(Net, self).__init__()
        self.conv1 = SplineConv(7, 32, dim=2, kernel_size=5)
        self.conv2 = SplineConv(32, 64, dim=2, kernel_size=5)
        self.fc1 = nn.Linear(64, 30)

    def forward(self, x, adj, slice):
        x = F.elu(self.conv1(adj, x))
        x = F.elu(self.conv2(adj, x))
        x = batch_average(x, slice)
        x = F.dropout(x, training=self.training)
        x = self.fc1(x)
        return F.log_softmax(x)


model = Net()
if torch.cuda.is_available():
    model = model.cuda()

optimizer = torch.optim.Adam(model.parameters(), lr=0.01)


def train(epoch):
    model.train()

    for data in train_loader:
        adj, slice = data['adj']['content'], data['adj']['slice'][:, 0]
        input, target = data['input'], data['target']

        if torch.cuda.is_available():
            adj, slice = adj.cuda(), slice.cuda()
            input, target = input.cuda(), target.cuda()

        input, target = Variable(input), Variable(target)

        optimizer.zero_grad()
        output = model(input, adj, slice)
        loss = F.nll_loss(output, target)
        loss.backward()
        optimizer.step()


def test(epoch, loader, string):
    model.eval()

    correct = 0
    num_examples = 0

    for data in loader:
        adj, slice = data['adj']['content'], data['adj']['slice'][:, 0]
        input, target = data['input'], data['target']
        num_examples += target.size(0)

        if torch.cuda.is_available():
            adj, slice = adj.cuda(), slice.cuda()
            input, target = input.cuda(), target.cuda()

        output = model(Variable(input), adj, slice)
        pred = output.data.max(1)[1]
        correct += pred.eq(target).cpu().sum()

    print('Epoch', epoch, string, correct / num_examples)


for epoch in range(1, 501):
    train(epoch)
    test(epoch, train_loader, 'Train Accuracy')
    test(epoch, test_loader, ' Test Accuracy')
