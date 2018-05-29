#include "Ipc.h"

void main() {

	LARGE_INTEGER frequency;        // ticks per second
	LARGE_INTEGER t1, t2;           // ticks
	double elapsedTime;

	// get ticks per second
	QueryPerformanceFrequency(&frequency);



	// compute and print the elapsed time in millisec
	

	cc::ipc::Ipc ipc;


	std::cout << "connecting" << std::endl;
	ipc.Connect();
	QueryPerformanceCounter(&t1);
	for (int i = 0; i < 1; ++i) {
		ipc.GetSyncDirectory();
	}
	QueryPerformanceCounter(&t2);

	std::cout << "took" << (t2.QuadPart - t1.QuadPart) * 1000.0 / frequency.QuadPart << std::endl;


	system("pause");
}