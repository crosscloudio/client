#include "utils/logging.h"
#include "utils/utils.h"

namespace cc {
namespace utils {

LoggingSingleton* LoggingSingleton::instance = nullptr;

std::wostream& LoggingSingleton::logStream()
{
	if (!instance)
		instance = new LoggingSingleton;

	return instance->logstream;
}

LoggingSingleton::LoggingSingleton() : logstream(std::wofstream(getCrossCloudSettingsPath() / path(L"logs/shext.log"), std::ostream::app))
{
}



}
}