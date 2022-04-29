import os
import pickle
import time
from io import StringIO

import numpy as np
import pandas as pd
import torch
from tqdm import tqdm

from facemap import utils

from . import datasets, facemap_network, model_loader, model_training
from . import pose_helper_functions as pose_utils
from . import transforms

"""
Base class for generating pose estimates.
Contains functions that can be used through CLI or GUI
Currently supports single video processing, whereas multi-view videos recorded simultaneously are processed sequentially.
"""


class Pose:
    def __init__(
        self,
        filenames=None,
        bodyparts=None,
        bbox=[],
        bbox_set=False,
        resize=False,
        add_padding=False,
        gui=None,
        GUIobject=None,
        net=None,
    ):
        self.gui = gui
        self.GUIobject = GUIobject
        if self.gui is not None:
            self.filenames = self.gui.filenames
        else:
            self.filenames = filenames
        self.cumframes, self.Ly, self.Lx, self.containers = utils.get_frame_details(
            self.filenames
        )
        self.nframes = self.cumframes[-1]
        self.pose_labels = None
        self.bodyparts = bodyparts
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.bbox = bbox
        self.bbox_set = bbox_set
        self.resize = resize
        self.add_padding = add_padding
        self.net = net
        self.finetuned_model = False

    def pose_prediction_setup(self):
        # Setup the model
        if self.net is None:
            self.load_model()
        # Setup the bounding box
        if not self.bbox_set:
            for i in range(len(self.Ly)):
                x1, x2, y1, y2 = 0, self.Ly[i], 0, self.Lx[i]
                self.bbox.append([x1, x2, y1, y2])

                # Update resize and add padding flags
                if x2 - x1 != y2 - y1:
                    self.add_padding = True
                if x2 - x1 != 256 or y2 - y1 != 256:
                    self.resize = True
                prompt = (
                    "No bbox set. Using entire frame view: {} and resize={}".format(
                        self.gui.bbox, self.resize
                    )
                )
                utils.update_mainwindow_message(
                    MainWindow=self.gui,
                    GUIobject=self.GUIobject,
                    prompt=prompt,
                    hide_progress=True,
                )
            self.bbox_set = True

    def run_all(self, plot=True):
        if self.finetuned_model:
            print("Using finetuned model for pose estimation")
        start_time = time.time()
        self.pose_prediction_setup()
        for video_id in range(len(self.filenames[0])):
            utils.update_mainwindow_message(
                MainWindow=self.gui,
                GUIobject=self.GUIobject,
                prompt="Processing video: {}".format(self.filenames[0][video_id]),
                hide_progress=True,
            )
            pred_data, metadata = self.predict_landmarks(video_id)
            dataFrame = self.write_dataframe(pred_data.cpu().numpy())
            savepath = self.save_pose_prediction(dataFrame, video_id)
            utils.update_mainwindow_message(
                MainWindow=self.gui,
                GUIobject=self.GUIobject,
                prompt="Saved pose prediction outputs to: {}".format(savepath),
                hide_progress=True,
            )
            print("Saved pose prediction outputs to:", savepath)
            # Save metadata to a pickle file
            if self.finetuned_model:
                metadata_file = (
                    os.path.splitext(savepath)[0] + "_FacemapFinetuned_metadata.pkl"
                )
            else:
                metadata_file = os.path.splitext(savepath)[0] + "_Facemap_metadata.pkl"
            with open(metadata_file, "wb") as f:
                pickle.dump(metadata, f, pickle.HIGHEST_PROTOCOL)
            if self.gui is not None:
                self.update_gui_pose(savepath, video_id)
        if plot and self.gui is not None:
            self.plot_pose_estimates()
        end_time = time.time()
        print("Pose estimation time elapsed:", end_time - start_time, "seconds")
        utils.update_mainwindow_message(
            MainWindow=self.gui,
            GUIobject=self.GUIobject,
            prompt="Pose estimation time elapsed: {} seconds".format(
                end_time - start_time
            ),
            hide_progress=True,
        )

    def update_gui_pose(self, savepath, video_id):
        if len(self.gui.poseFilepath) == 0:
            self.gui.poseFilepath.append(savepath)
        else:
            self.gui.poseFilepath[video_id] = savepath
        self.gui.load_keypoints()
        self.gui.keypoints_checkbox.setChecked(False)
        self.gui.keypoints_checkbox.setChecked(True)
        self.gui.start()

    def run_subset(self, subset_ind=None):
        """
        Run pose estimation on a random subset of frames
        """
        if self.finetuned_model:
            print("Using finetuned model for pose estimation")
        self.pose_prediction_setup()
        if subset_ind is None:
            # Select a random subset of frames
            subset_size = int(self.nframes / 10)
            subset_ind = np.random.choice(self.nframes, subset_size, replace=False)
            subset_ind = np.sort(subset_ind)

        utils.update_mainwindow_message(
            MainWindow=self.gui,
            GUIobject=self.GUIobject,
            prompt="Processing video: {}".format(self.filenames[0][0]),
            hide_progress=True,
        )
        pred_data, _ = self.predict_landmarks(0, frame_ind=subset_ind)
        utils.update_mainwindow_message(
            MainWindow=self.gui,
            GUIobject=self.GUIobject,
            prompt="Finished processing subset of video",
            hide_progress=True,
        )
        return pred_data, subset_ind, self.bbox

    def train(
        self,
        image_data,
        keypoints_data,
        num_epochs,
        batch_size,
        learning_rate,
        weight_decay,
    ):
        """
        Train the model
        Parameters
        ----------
        image_data: numpy array
            Array of images
        keypoints_data: numpy array
            Array of keypoints
        num_epochs: int
            Number of epochs for training
        batch_size: int
            Batch size for training
        learning_rate: float
            Learning rate for training
        weight_decay: float
            Weight decay for training
        Returns
        -------
        model: torch.nn.Module
            Trained/finetuned model
        """
        # Create a dataset object for training
        dataset = datasets.FacemapDataset(
            image_data=image_data,
            keypoints_data=keypoints_data,
            bbox=self.bbox[0],
        )
        # Create a dataloader object for training
        dataloader = torch.utils.data.DataLoader(
            dataset, batch_size=batch_size, shuffle=True
        )
        # Use preprocessed data to train the model
        self.net = model_training.train(
            dataset,
            dataloader,
            self.net,
            num_epochs,
            learning_rate,
            weight_decay,
            self.gui,
            self.GUIobject,
        )
        self.finetuned_model = True
        print("Model training complete!")
        return self.net

    def save_model(self, model_filepath):
        torch.save(self.net.state_dict(), model_filepath)
        model_loader.copy_to_models_dir(model_filepath)
        return model_filepath

    def write_dataframe(self, data, selected_frame_ind=None):
        scorer = "Facemap"
        bodyparts = self.bodyparts
        # Create an empty dataframe
        for index, bodypart in enumerate(bodyparts):
            columnindex = pd.MultiIndex.from_product(
                [[scorer], [bodypart], ["x", "y", "likelihood"]],
                names=["scorer", "bodyparts", "coords"],
            )
            if selected_frame_ind is None:
                frame = pd.DataFrame(
                    np.nan, columns=columnindex, index=np.arange(self.cumframes[-1])
                )
            else:
                frame = pd.DataFrame(
                    np.nan, columns=columnindex, index=selected_frame_ind
                )
            if index == 0:
                dataFrame = frame
            else:
                dataFrame = pd.concat([dataFrame, frame], axis=1)

        # Fill dataframe with data
        dataFrame.iloc[:, ::3] = data[:, :, 0]
        dataFrame.iloc[:, 1::3] = data[:, :, 1]
        dataFrame.iloc[:, 2::3] = data[:, :, 2]

        return dataFrame

    def predict_landmarks(self, video_id, frame_ind=None):
        """
        Predict labels for all frames in video and save output as .h5 file
        """
        nchannels = 1

        if (
            torch.cuda.is_available()
        ):  # TODO - Support other batch sizes depending on GPU memory and CPU
            batch_size = 1
        else:  # TODO - Optimize for CPU usage
            batch_size = 1

        if frame_ind is None:
            total_frames = self.cumframes[-1]
            frame_ind = np.arange(total_frames)
        else:
            total_frames = len(frame_ind)

        # Create array for storing predictions
        pred_data = torch.zeros(total_frames, len(self.net.bodyparts), 3)

        # Store predictions in dataframe
        self.net.eval()
        start = 0
        end = batch_size
        # Get bounding box for the video
        x1, _, y1, _ = self.bbox[video_id]
        inference_time = 0

        print("Using params:")
        print("BBOX:", self.bbox[video_id])
        print("resize:", self.resize)
        print("padding:", self.add_padding)

        progress_output = StringIO()
        with tqdm(
            total=total_frames, unit="frame", unit_scale=True, file=progress_output
        ) as pbar:
            while start != total_frames:  #  for analyzing entire video

                # Pre-pocess images
                imall = np.zeros(
                    (batch_size, nchannels, self.Ly[video_id], self.Lx[video_id])
                )
                cframes = np.array(frame_ind[start:end])
                utils.get_frames(imall, self.containers, cframes, self.cumframes)

                # Inference time includes: pre-processing, inference, post-processing
                t0 = time.time()

                # Pre-process images
                imall, postpad_shape, pads = transforms.preprocess_img(
                    imall,
                    self.bbox[video_id],
                    self.add_padding,
                    self.resize,
                    device=self.net.device,
                )

                # obj = pose_utils.test_popup(imall[0].squeeze().detach().cpu().numpy(), self.gui, title="Post-processing {}".format(start))

                # Run inference
                xlabels, ylabels, likelihood = pose_utils.predict(
                    self.net, imall, smooth=False
                )

                xlabels, ylabels = transforms.adjust_keypoints(
                    xlabels,
                    ylabels,
                    crop_xy=(x1, y1),
                    padding=pads,
                    current_size=(256, 256),
                    desired_size=postpad_shape,
                )

                # Add predictions to array
                pred_data[start:end, :, 0] = xlabels
                pred_data[start:end, :, 1] = ylabels
                pred_data[start:end, :, 2] = likelihood

                # Update progress bar and inference time
                inference_time += time.time() - t0
                pbar.update(batch_size)
                start = end
                end += batch_size
                end = min(end, total_frames)
                # Update progress bar for every 5% of the total frames
                if (end) % np.floor(total_frames * 0.05) == 0:
                    utils.update_mainwindow_progressbar(
                        MainWindow=self.gui,
                        GUIobject=self.GUIobject,
                        s=progress_output,
                        prompt="Pose prediction progress:",
                    )

        if batch_size == 1:
            inference_speed = total_frames / inference_time
            print("Inference speed:", inference_speed, "fps")

        metadata = {
            "batch_size": batch_size,
            "image_size": (self.Ly, self.Lx),
            "bbox": self.bbox[video_id],
            "total_frames": total_frames,
            "bodyparts": self.net.bodyparts,
            "inference_speed": inference_speed,
        }
        return pred_data, metadata

    def save_pose_prediction(self, dataFrame, video_id):
        # Save prediction to .h5 file
        if self.gui is not None:
            basename = self.gui.save_path
            _, filename = os.path.split(self.filenames[0][video_id])
            videoname, _ = os.path.splitext(filename)
        else:
            basename, filename = os.path.split(self.filenames[0][video_id])
            videoname, _ = os.path.splitext(filename)
        if self.finetuned_model:
            poseFilepath = os.path.join(
                basename, videoname + "_FacemapPoseFinetuned.h5"
            )
        else:
            poseFilepath = os.path.join(basename, videoname + "_FacemapPose.h5")
        dataFrame.to_hdf(poseFilepath, "df_with_missing", mode="w")
        return poseFilepath

    def plot_pose_estimates(self):
        # Plot labels
        self.gui.is_pose_loaded = True
        self.gui.load_keypoints()
        self.gui.keypoints_checkbox.setChecked(True)

    def load_model(self, model_state_file=None):
        """
        Load pre-trained model for keypoints prediction
        """
        if model_state_file is None:
            model_state_file = model_loader.get_model_state_path()
        else:
            self.finetuned_model = True
        model_params_file = model_loader.get_model_params_path()
        if torch.cuda.is_available():
            print("Using cuda as device")
        else:
            print("Using cpu as device")
        print("LOADING MODEL....", model_params_file)
        utils.update_mainwindow_message(
            MainWindow=self.gui,
            GUIobject=self.GUIobject,
            prompt="Loading model... {}".format(model_params_file),
        )
        model_params = torch.load(model_params_file, map_location=self.device)
        self.bodyparts = model_params["params"]["bodyparts"]
        channels = model_params["params"]["channels"]
        kernel_size = 3
        nout = len(self.bodyparts)  # number of outputs from the model
        net = facemap_network.FMnet(
            img_ch=1,
            output_ch=nout,
            labels_id=self.bodyparts,
            channels=channels,
            kernel=kernel_size,
            device=self.device,
        )
        net.load_state_dict(torch.load(model_state_file, map_location=self.device))
        net.to(self.device)
        self.net = net
