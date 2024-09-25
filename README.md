# BP_To_CPP
EXPERIMENTAL program that converts Unreal Engine 4.27 blueprint graphs into C++

EXPERIMENTAL
This is meant for advanced C++/Blueprint users only, there are a lot of nuances with converting blueprint into C++, such as handling multiple input execution connections into a single node (which will cause this program to purposely error).

How to use:
1. Copy 1 blueprint graph with Ctrl+C / Cmd+C
2. Run the python code
3. The C++ code is then copied to your clipboard and also written to output.cpp in the working directory
