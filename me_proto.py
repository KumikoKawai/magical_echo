#!/usr/bin/python


import pyaudio
import struct
import math
import os
import sys
import time
import wave
import subprocess


INITIAL_TAP_THRESHOLD = 0.020
#FORMAT = pyaudio.paInt16
SHORT_NORMALIZE = (1.0/32768.0)
#CHANNELS = 1
RATE = 44100
INPUT_BLOCK_TIME = 0.05
INPUT_FRAMES_PER_BLOCK = int(RATE*INPUT_BLOCK_TIME)
# if we get this many noisy blocks in a row, increase the threshold
OVERSENSITIVE = 150.0/INPUT_BLOCK_TIME
# if we get this many quiet blocks in a row, decrease the threshold
UNDERSENSITIVE = 12.0/INPUT_BLOCK_TIME
MAX_TAP_BLOCKS = 0.15/INPUT_BLOCK_TIME
CHUNK = 1024


def get_rms( block ):
    # RMS amplitude is defined as the square root of the 
    # mean over time of the square of the amplitude.
    # so we need to convert this string of bytes into 
    # a string of 16-bit samples...

    # we will get one short out for each 
    # two chars in the string.
    count = len(block)/2
    format = "%dh"%(count)
    shorts = struct.unpack( format, block )

    # iterate over the block.
    sum_squares = 0.0
    for sample in shorts:
        # sample is a signed short in +/- 32768. 
        # normalize it to 1.0
        n = sample * SHORT_NORMALIZE
        sum_squares += n*n

    return math.sqrt( sum_squares / count )


#### get input sentence and break into words
#   eg. this is a test => 0.wav(this) 1.wav(is) 2.wav(a) 3.wav(test)
######
def get_word():
    text2read = raw_input('Please enter the sentence you want to read: ')
    words = text2read.split(" ")
    count = 0
    for w in words:
        textToWav(w,str(count))
        count +=1
    return words

# from TTS save words as wav file
def textToWav(text,file_name):
   subprocess.call(["espeak", "-w"+file_name+".wav", text])

######
#   TapTester. progress with voice (mic->progress, play->.wav)
#####
class TapTester(object):
    def __init__(self,wordlen,word):
        self.pa = pyaudio.PyAudio()
        wf = wave.open("0.wav", "rb") # get the sample of word voice file
        self.stream = self.open_mic_stream(wf)
        self.tap_threshold = INITIAL_TAP_THRESHOLD
        self.noisycount = MAX_TAP_BLOCKS+1 
        self.quietcount = 0 
        self.errorcount = 0
        self.wordcount  = 0
        self.wordlen = wordlen
        self.word = word
	self.do = True

    # voice progress stop 
    def stop(self):
        self.do = False
        self.stream.close()

    # search for input mic
    def find_input_device(self):
        device_index = None            
        for i in range( self.pa.get_device_count() ):     
            devinfo = self.pa.get_device_info_by_index(i)   
            print( "Device %d: %s"%(i,devinfo["name"]) )

            for keyword in ["mic","input"]:
                if keyword in devinfo["name"].lower():
                    print( "Found an input: device %d - %s"%(i,devinfo["name"]) )
                    device_index = i
                    return device_index

        if device_index == None:
            print( "No preferred input found; using default input device." )

        return device_index

    ## init stream format
    def open_mic_stream( self ,wf):
        device_index = self.find_input_device()

        stream = self.pa.open(   format = self.pa.get_format_from_width(wf.getsampwidth()),
                                 channels = wf.getnchannels(),
                                 rate = wf.getframerate(),
                                 input = True,
                                 output = True,
                                 input_device_index = device_index,
                                 frames_per_buffer = INPUT_FRAMES_PER_BLOCK)

        return stream

    # play word wave file
    def do_speak(self):
        print ("word: "+self.word[self.wordcount])
        wf = wave.open(str(self.wordcount)+".wav","rb")
        data = wf.readframes(CHUNK)
        while data !='':
            self.stream.write(data)
            data = wf.readframes(CHUNK)


    # process when receive triger
    def tapDetected(self):
        self.do_speak()
        self.wordcount += 1
        if self.wordcount >= self.wordlen:
            self.stop()


    # do listen to mic and progress
    def listen(self):
        try:
            block = self.stream.read(INPUT_FRAMES_PER_BLOCK)
        except IOError,e:

            self.errorcount += 1
            print( "(%d) Error recording: %s"%(self.errorcount,e) )
            self.noisycount = 1
            return

        amplitude = get_rms( block )
        if amplitude < self.tap_threshold:
            # quiet block
            self.quietcount += 1
            self.noisycount = 0
            if self.quietcount > OVERSENSITIVE:
                # turn down the thresold
                self.tap_threshold *= 0.9
        else:            
            # noisy block.

            if 1 <self.quietcount:
                self.tapDetected()

            self.noisycount += 1
            self.quietcount = 0
            if self.noisycount > UNDERSENSITIVE:
                # turn up the threshold
                self.tap_threshold *= 1.4





if __name__ == "__main__":
    wd = get_word()
    tt = TapTester(len(wd),wd)

    for i in range(500):
        tt.listen()
        if not tt.do:
            break


