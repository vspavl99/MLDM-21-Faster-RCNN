from progress.bar import IncrementalBar
import torch
import json

DIR_TO_SAVE_MODELS = 'models'
DIR_TO_SAVE_LOGS = 'logs'


class ModelTrainer:
    def __init__(self, model, optimizer, scheduler, device, dataloaders):

        self.model = model
        self.device = device
        self.model = model.to(device)
        self.optimizer = optimizer

        self.scheduler = scheduler
        self.device = device

        self.losses = {'train': [], 'val': []}
        self.dataloaders = dataloaders

        # self.metrics = {'AP': accuracy_score, "BAP": balanced_accuracy_score}
        # self.metrics_values = {
        #     phase: {name: [] for name in self.metrics.keys()} for phase in ['train', 'val']
        # }
        # if best_score is not None:
        #     self.best_score = best_score
        # else:
        #     self.best_score = np.array([-np.inf for _ in self.metrics.keys()])

    def step(self, phase):
        epoch_loss = 0.0

        self.model.train() if phase == 'train' else self.model.eval()

        dataloader = self.dataloaders[phase]
        bar = IncrementalBar('Countdown', max=len(dataloader))

        self.optimizer.zero_grad()
        for i, batch_data in enumerate(dataloader):

            batch_images = [data['image'] for data in batch_data]
            batch_images = torch.stack(batch_images, dim=0).to(self.device)

            # batch_boxes = [torch.Tensor(data['bboxes']).to(self.device) for data in batch_data]
            # batch_classes = [torch.Tensor(data['class_labels']).to(self.device) for data in batch_data]

            batch_targets = [
                {
                    'boxes': torch.Tensor(data['bboxes']).to(self.device),
                    'labels': torch.Tensor(data['class_labels']).to(self.device)
                }
                for data in batch_data
            ]

            with torch.set_grad_enabled(phase == 'train'):

                batch_predictions, loss = self.model(batch_images, batch_targets)

                loss = sum(value for key, value in loss.items())

                if phase == "train":
                    loss.backward()
                    self.optimizer.step()
                    self.optimizer.zero_grad()

                epoch_loss += loss.item()
                bar.next()

            del batch_images, batch_targets, batch_predictions, loss

        bar.finish()

        epoch_loss = epoch_loss / len(dataloader)

        self.losses[phase].append(epoch_loss)

        torch.cuda.empty_cache()

        return epoch_loss

    def train(self, num_epochs):
        state = None
        bar = IncrementalBar('Countdown', max=num_epochs)

        for epoch in range(num_epochs):
            bar.next()

            loss, metric = self.step('train')

            print(f'Epoch {epoch} | train_loss {loss} | train_metric {metric}')

            state = {
                'epoch': epoch,
                'state_dict': self.model.state_dict(),
                'optimizer': self.optimizer.state_dict(),
                'scheduler': self.scheduler.state_dict()
            }

            loss, metric = self.step('val')

            print(f'Epoch {epoch} | val_loss {loss} | val_metric {metric}')

            self.scheduler.step(loss)

        bar.finish()
        # saving last epoch
        print('-' * 10 + str(num_epochs) + 'passed' + '-' * 10)
        torch.save(state, "{}/model_epoch_{}_score_{:.4f}.pth".format(DIR_TO_SAVE_MODELS, num_epochs, 0.1))


from model.FasterRCNN import FasterRCNN
from torch.optim import Adam
from train.dataloader import ConfigDataset, get_dataloader, DatasetFasterRCNN
from pathlib import Path


if __name__ == '__main__':

    dataloaders = get_dataloader(
        path_train_csv=Path('../data/annotation.csv'),
        path_val_csv=Path('../data/annotation2.csv'),
        shuffle=False, batch_size=2
    )

    faster_rcnn = FasterRCNN(stage='train')
    device = torch.device('cuda:0' if torch.cuda.is_available() else 'cpu')

    optimizer = Adam(faster_rcnn.parameters())
    scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(optimizer, factor=0.9, mode="min", patience=3, verbose=True)

    model_train = ModelTrainer(faster_rcnn, optimizer, scheduler, device, dataloaders)
    model_train.train(20)


