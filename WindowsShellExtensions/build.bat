
rem source vars
set GENERATOR="Visual Studio 14 2015 Win64"

cmake -G%GENERATOR% ..
cmake --build . --config release
