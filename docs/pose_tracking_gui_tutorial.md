# Pose tracking **(GUI)** :mouse:

<img src="../figs/tracker.gif" width="100%" height="500" title="Tracker" alt="tracker" algin="middle" vspace = "10">

The latest python version is integrated with Facemap network for tracking 14 distinct keypoints on mouse face and an additional point for tracking paw. The keypoints can be tracked from different camera views (some examples shown below). 

<p float="middle">
<img src="../figs/mouse_face1_keypoints.png"  width="310" height="290" title="View 1" alt="view1" align="left" vspace = "10" hspace="30" style="border: 0.5px solid white"  />
<img src="../figs/mouse_face0_keypoints.png" width="310" height="290" title="View 2" alt="view2" algin="right" vspace = "10" style="border: 0.5px solid white">
</p>

For pose tracking using GUI after following the [installation instructions](installation.md), proceed with the following steps:

1. Load video 
    - Select `File` from the menu bar
    - For processing single video, select `Load single movie file`
    - Alternatively, for processing multiple videos, select `Open folder of movies` and then select the files you want to process. Please note multiple videos are processed sequentially.
2. Select output folder
    - Use the file menu to `Set output folder`. 
    - The processed keypoints file will be saved in the selected output folder with an extension of `.h5` and corresponding metadata file with extension `.pkl`.
3. Choose processing options 
    - Check at least one of the following boxes:
        - `Keypoints` for face pose tracking.
        - `motSVD` for SVD processing of difference across frames over time.
        - `movSVD` for SVD processing of raw movie frames.
    - Click `process` button and monitor progress bar at the bottom of the window to see updates.
4. Select ROI/bounding box for face
    - Once you hit `process`, a dialog box will appear for selecting a bounding box for the face. The keypoints will be tracked in the selected bounding box. Please ensure that the bouding box is focused on the face where all the keypoints shown above will be visible. See example frames [here](figs/mouse_views.png). Once the bounding box is focused, click 'Done' to continue.
    - Alternatively, if you wish to use the entire frame for the mouse then click 'Skip' to continue.
    - If a 'Face (pose)' ROI has already been selected using the dropdown menu for ROIs the bounding box will be automatically selected and the keypoints will be tracked in the selected ROI.

The videos will be processed in the order they are listed in the file list and output will be saved in the output folder. Following is an example gif demonstrating the above mentioned steps for tracking keypoints in a video.


