# quick-share
## Introduction
QuickShare is a web project based on a Python back-end, which is aimed at transmitting files from one to one/more via P2P pattern.
As we design, it is used in the situations - a lecture, a presentation, a meeting, an exhibition, and even a temporary cooperation - where there is a need for quick and temporary file-transmission without adding each others' WeChat friends or uploading files onto a cloud storage.

## Security and Privacy
The transmission channel is protected with Https pattern, and the files are all encrypted during transmission (namely with end-to-end encryption). In the process of file transmission, we only save the metadata of transmission persistently on the server besides the minimum essential data to sustain the function of QuickShare. 

## Authorization
To act as a sender of files, you should login a valid account while you can act as a receiver with either login status or non-login status.


