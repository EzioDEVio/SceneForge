#!/bin/bash
# sheet.sh in.mp4 out.png every_s cols scale_w
ffmpeg -v error -y -i "$1" -vf "fps=1/$3,scale=$5:-1,tile=$4x4:padding=6:color=white" -frames:v 1 "$2"
