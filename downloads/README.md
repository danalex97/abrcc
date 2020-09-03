# Video download utilities

The `downloads` folder contains the following scripts:
- `video_downloader.py` - Download from Youtube and create a DASH.js compliant video.
- `export.py` - Export a video and video configuration for usage in the backend.
- `plot.py` - Plot the per-segment VMAF video structure of multiple videos.

### Installation

To install all the dependencies, run the following script:
```bash
./install.sh
```

### Usage

- The video downloader can be used as below. The video will be stored in `videos/[video_name]/tracks`, while the JSON configuration will be generated in the file `videos/[video_name]/vmaf.json`.

```bash
usage: video_downloader.py [-h] [-s SEGMENT] [-vmaf] url video

Download and make a DASH.js compliant video.

positional arguments:
  url                   Video url.
  video                 Name of the video.

optional arguments:
  -s SEGMENT, --segment-size SEGMENT
                        Segment size in ms.
  -vmaf                 Generate VMAF configuration.
```


- Export utility:

```bash
usage: export.py [-h] video

Prepare and export JSON compatible with QUIC backend. Exports the DASH video segments to the backend.

positional arguments:
  video       Name of the video.
```

- Plot utility:

```bash
usage: plot.py [-h] [video [video ...]]

Plot VMAF structure for a list of videos.

positional arguments:
  video       Name of the video.
```



Note the **video name** has to be the same across all 3 of the scripts.
