# bw2color
Project for the course Artificial Intelligence in Practice.
Use cGAN to colorize Anime images.
Reference: https://arxiv.org/abs/1611.07004

## project structure

```vim

├── data/               // original dataset
├── model/              // saved model
├── out/                // preprocessed image
├── test_result/        // test result image
├── training_result/    // training result image 
├── tfrecord/           // tfrecord folder
├── backward.py         // nn backward
├── forward.py          // nn forward
├── generateds.py       // tfrecord generate and get
├── test.py             // result test
└── tools           
    ├── preprocess.py   // cut image
    ├── run.sh          // py run script
    ├── upload.sh       // upload py files to server
    └── wallpaper.py    // spiders
```

## Usage

download [wall.alphacoders.com](https://wall.alphacoders.com) thumb image

    cd bw2color
    python tools/wallpaper.py

crop downloaded image to 256x256 and convert to grey

```bash
cd bw2color
# basic use
python tools/preprocess.py
# set data dir
python tools/preprocess.py --data [data dir] --save  [output dir]
# set process method
python tools/preprocess.py --method gray
python tools/preprocess.py --method sketch --mod_path [mod file path]
```

generate tfrecord

    python generateds.py
    
train

    python backward.py

test

    python test.py

