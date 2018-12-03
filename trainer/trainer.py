import numpy as np
import torch
from base import BaseTrainer
from utils.bbox import Toolbox
from utils.visualize import Visualizer
class Trainer(BaseTrainer):
    """
    Trainer class

    Note:
        Inherited from BaseTrainer.
        self.optimizer is by default handled by BaseTrainer based on config.
    """
    def __init__(self, model, loss, metrics, resume, config,
                 data_loader, toolbox: Toolbox, valid_data_loader=None, train_logger=None):
        super(Trainer, self).__init__(model, loss, metrics, resume, config, train_logger)
        self.config = config
        self.batch_size = data_loader.batch_size
        self.data_loader = data_loader
        self.valid_data_loader = valid_data_loader
        self.valid = True if self.valid_data_loader is not None else False
        self.log_step = int(np.sqrt(self.batch_size))
        self.toolbox = toolbox
        self.visdom = Visualizer(env='FOTS')

    def _to_tensor(self, *tensors):
        t = []
        for __tensors in tensors:
            t.append(__tensors.to(self.device))
        return t

    def _eval_metrics(self, output, target, mask):
        acc_metrics = np.zeros(len(self.metrics))
        output = output.cpu().data.numpy()
        target = target.cpu().data.numpy()
        output = np.argmax(output, axis=1)
        for i, metric in enumerate(self.metrics):
            acc_metrics[i] += metric(output, target)
        return acc_metrics

    def _train_epoch(self, epoch):
        """
        Training logic for an epoch

        :param epoch: Current training epoch.
        :return: A log that contains all information you want to save.

        Note:
            If you have additional information to record, for example:
                > additional_log = {"x": x, "y": y}
            merge it with log before return. i.e.
                > log = {**log, **additional_log}
                > return log

            The metrics in log must have the key 'metrics'.
        """
        # TODO 现在不知道这个Model Train都做了什么
        self.model.train()

        total_loss = 0
        total_metrics = np.zeros(len(self.metrics))
        for batch_idx, gt in enumerate(self.data_loader):
            img, score_map, geo_map, training_mask, transcript = gt
            # 根据不同的设备做了tensor的转换
            img, score_map, geo_map, training_mask = self._to_tensor(img, score_map, geo_map, training_mask)
            recog_map = None

            self.optimizer.zero_grad()
            # TODO 这个Model不知道是在做什么？感觉是带入到模型出结果的意思
            pred_score_map, pred_geo_map, pred_recog_map = self.model(img)

            loss = self.loss(score_map, pred_score_map, geo_map, pred_geo_map, pred_recog_map, recog_map, training_mask)
            loss.backward()
            self.optimizer.step()

            total_loss += loss.item()
            #total_metrics += self._eval_metrics(output, target)

            total_metrics += 0

            if self.verbosity >= 2 and batch_idx % self.log_step == 0:
                self.logger.info('Train Epoch: {} [{}/{} ({:.0f}%)] Loss: {:.6f}'.format(
                    epoch,
                    batch_idx * self.data_loader.batch_size,
                    len(self.data_loader) * self.data_loader.batch_size,
                    100.0 * batch_idx / len(self.data_loader),
                    loss.item()))

        # TODO 这个应该是个可视化的工具，需要研究下
        self.visdom.plot('train_loss', total_loss / len(self.data_loader))
        log = {
            'loss': total_loss / len(self.data_loader),
            'metrics': (total_metrics / len(self.data_loader)).tolist()
        }

        if self.valid:
            val_log = self._valid_epoch()
            log = {**log, **val_log}

        return log

    def _valid_epoch(self):
        """
        Validate after training an epoch

        :return: A log that contains information about validation

        Note:
            The validation metrics in log must have the key 'val_metrics'.
        """
        self.model.eval()
        total_val_loss = 0
        total_val_metrics = np.zeros(len(self.metrics))
        with torch.no_grad():
            for batch_idx, gt in enumerate(self.valid_data_loader):
                img, score_map, geo_map, training_mask, transcript = gt
                img, score_map, geo_map, training_mask = self._to_tensor(img, score_map, geo_map, training_mask)
                recog_map = None

                pred_score_map, pred_geo_map, pred_recog_map = self.model(img)

                loss = self.loss(score_map, pred_score_map, geo_map, pred_geo_map, pred_recog_map, recog_map,
                                 training_mask)

                total_val_loss += loss.item()

                output = (pred_score_map, pred_geo_map, pred_recog_map)
                target = (score_map, geo_map, recog_map)
                #total_val_metrics += self._eval_metrics(output, target, training_mask) #TODO: should add AP metric
        self.visdom.plot('val_loss', total_val_loss / len(self.valid_data_loader))
        return {
            'val_loss': total_val_loss / len(self.valid_data_loader),
            'val_metrics': (total_val_metrics / len(self.valid_data_loader)).tolist()
        }
