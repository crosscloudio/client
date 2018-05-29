/**
* (C) 2016 CrossCloud GmbH
*/

#ifndef LOGGING_H
#define LOGGING_H

#include <iomanip>

#pragma once

#ifdef _DEBUG
#define LOGGING
#endif

#ifdef LOGGING
#define LOG_FUN_RETURN(x) LOG_MESSAGE( L"return " << __FUNCTIONW__ <<  " :" << std::hex << x << std::endl); return x
#define LOG_FUN_ENTRY LOG_MESSAGE(L"enter " << __FUNCTIONW__ << std::endl)
#define LOG_MESSAGE(x) cc::utils::LoggingSingleton::logStream() << GetCurrentThreadId() << "|" <<  x ; cc::utils::LoggingSingleton::logStream().flush()
#else
#define LOG_FUN_ENTRY
#define LOG_FUN_RETURN(x) return x
#define LOG_MESSAGE(x)
#endif

#include <ostream>
#include <fstream>


namespace cc {	namespace utils {


class LoggingSingleton
{
public:
	static std::wostream& logStream();

private:
	LoggingSingleton();
	static LoggingSingleton* instance;
	std::wofstream logstream;
};


}
}
#endif //LOGGING_H
