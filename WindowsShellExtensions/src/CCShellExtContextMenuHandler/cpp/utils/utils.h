#pragma once

#include <string>
#include <Windows.h>
#include <filesystem>


namespace cc {
	typedef std::tr2::sys::path path;
	namespace utils
	{
		wchar_t* charToWChar(const char *c);
		char* wCharToChar(const wchar_t *wc);
		bool existsFile(const std::wstring& path);
		path getModulePath();
		path getCrossCloudLockFilePath();
		path getCrossCloudSettingsPath();
		path getCrossCloudProgramPath();

		std::wstring utf8_to_wstring(std::string const&);
		std::string wstring_to_utf8(std::wstring const&);

		bool path_contains_file(path dir, path file);

		bool crossCloudRunning();
	}
}
