# BP_To_CPP
EXPERIMENTAL program that converts Unreal Engine 4.27 blueprint graphs into C++

EXPERIMENTAL
This is meant for advanced C++/Blueprint users only, there are a lot of nuances with converting blueprint into C++, such as handling multiple input execution connections into a single node (which will cause this program to purposely error).

How to use:
1. Click and drag to box select 1 blueprint graph (The program simply tries to find the first node that has an output exec pin and no input exec pin)
2. Copy with Ctrl+C / Cmd+C
3. Run BP_to_CPP.py
4. The C++ code is then copied to your clipboard and also written to output.cpp in the working directory
5. Additional instructions found at the top of the BP_to_CPP.py
