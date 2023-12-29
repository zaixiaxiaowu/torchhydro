"""
Author: Xinzhuo Wu
Date: 2023-09-30 1:20:18
LastEditTime: 2023-12-29 11:05:57
LastEditors: Xinzhuo Wu
Description: A pytorch dataset class; references to https://github.com/neuralhydrology/neuralhydrology
FilePath: \torchhydro\torchhydro\datasets\data_sets.py
Copyright (c) 2021-2022 Wenyu Ouyang. All rights reserved.
"""
import torch
from torch import nn


class TimeDistributed(nn.Module):
    def __init__(self, layer):
        super(TimeDistributed, self).__init__()
        self.layer = layer

    def forward(self, x):
        outputs = []
        for t in range(x.size(1)):
            xt = x[:, t, :]
            output = self.layer(xt)
            outputs.append(output.unsqueeze(1))
        outputs = torch.cat(outputs, dim=1)
        return outputs


class SppLayer(nn.Module):
    def __init__(self, out_pool_size):
        """
        out_pool_size: a int vector of expected output size of max pooling layer
        """
        super(SppLayer, self).__init__()
        self.out_pool_size = out_pool_size
        self.pools = []
        for i in range(len(out_pool_size)):
            pool_i = nn.AdaptiveMaxPool2d(out_pool_size[i])
            self.pools.append(pool_i)

    def forward(self, previous_conv):
        """
        Parameters
        ----------
        previous_conv
            a tensor vector of previous convolution layer

        Returns
        -------
        torch.Tensor
            a tensor vector with shape [1 x n] is the concentration of multi-level pooling
        """

        num_sample = previous_conv.size(0)
        channel_size = previous_conv.size(1)
        out_pool_size = self.out_pool_size
        for i in range(len(out_pool_size)):
            maxpool = self.pools[i]
            x = maxpool(previous_conv)
            if i == 0:
                spp = x.view(num_sample, channel_size, -1)
            else:
                spp = torch.cat((spp, x.view(num_sample, channel_size, -1)), -1)
        return spp


class SPP_LSTM_Model(nn.Module):
    def __init__(self, seq_length, forecast_length, n_output, n_hidden_states, dropout):
        super(SPP_LSTM_Model, self).__init__()

        self.conv1 = TimeDistributed(
            nn.Conv2d(
                in_channels=1,
                out_channels=32,
                kernel_size=1,
                padding="same",
            )
        )

        self.conv2 = TimeDistributed(
            nn.Conv2d(
                in_channels=32,
                out_channels=16,
                kernel_size=3,
                padding="same",
                bias=True,
            )
        )

        self.conv3 = TimeDistributed(
            nn.Conv2d(
                in_channels=16,
                out_channels=16,
                kernel_size=3,
                padding="same",
                bias=True,
            )
        )

        self.maxpool1 = TimeDistributed(nn.MaxPool2d(kernel_size=2, stride=(2, 2)))

        self.conv4 = TimeDistributed(
            nn.Conv2d(
                in_channels=16,
                out_channels=32,
                kernel_size=3,
                padding="same",
                bias=True,
            )
        )

        self.conv5 = TimeDistributed(
            nn.Conv2d(
                in_channels=32,
                out_channels=32,
                kernel_size=3,
                padding="same",
                bias=True,
            )
        )

        self.maxpool2 = TimeDistributed(SppLayer([4, 2, 1]))

        self.dropout = nn.Dropout(dropout)

        self.lstm = nn.LSTM(
            input_size=21 * 32, hidden_size=n_hidden_states, batch_first=True
        )

        self.dense = nn.Linear(in_features=n_hidden_states, out_features=n_output)

        self.forecast_length = forecast_length

    def forward(self, x):
        #  print(x.shape)
        x = torch.squeeze(x, dim=1)
        # print(x.shape)
        x = self.conv1(x)
        x = torch.relu(x)
        x = self.conv2(x)
        x = torch.relu(x)
        x = self.conv3(x)
        x = torch.relu(x)
        x = self.maxpool1(x)
        x = self.conv4(x)
        x = torch.relu(x)
        x = self.conv5(x)
        x = torch.relu(x)
        x = self.maxpool2(x)
        x = self.dropout(x)
        # print(x.shape)
        x = x.view(x.shape[0], x.shape[1], -1)
        # print(x.shape)
        x, _ = self.lstm(x)
        # print(x.shape)
        x = self.dense(x)
        x = x[:, -self.forecast_length :, :]
        # print(x.shape)
        return x
        # return x.unsqueeze(2).transpose(0, 1)


class SPP_LSTM_Model_2(nn.Module):
    def __init__(self, seq_length, forecast_length, n_output, n_hidden_states, dropout):
        super(SPP_LSTM_Model_2, self).__init__()
        self.conv1 = nn.Conv2d(
            in_channels=1,
            out_channels=32,
            kernel_size=(3, 3),
            padding="same",
        )

        self.leaky_relu = nn.LeakyReLU(0.01)

        self.lstm = nn.LSTM(
            input_size=32 * 5, hidden_size=n_hidden_states, batch_first=True
        )

        self.dropout = nn.Dropout(dropout)

        self.fc = nn.Linear(n_hidden_states, n_output)

        self.spp = SppLayer([2, 1])

        self.length = seq_length + forecast_length
        self.forecast_length = forecast_length

    def forward(self, x):
        x = torch.squeeze(x, dim=1)
        x = x.view(-1, x.shape[2], x.shape[3], x.shape[4])
        x = self.conv1(x)
        x = self.leaky_relu(x)
        x = self.spp(x)
        x = x.view(x.shape[0], -1)
        x = x.view(int(x.shape[0] / (self.length)), self.length, -1)
        x, _ = self.lstm(x)
        x = self.dropout(x)
        x = self.fc(x)
        return x[:, -self.forecast_length :, :]
