#include "utils.h"
#include "logging.h"
#include <Shlwapi.h>
#include <Shlobj.h>
#include <stdlib.h>
#include <string>
#include <sstream>
#include <sys/stat.h>
#include <locale>
#include <codecvt>
#include <filesystem>

extern HMODULE g_hInst;

namespace cc
{
namespace utils
{

	wchar_t* charToWChar(const char* c)
	{
		const size_t cSize = strlen(c) + 1;
		wchar_t* wc = new wchar_t[cSize];
		size_t convertedChars = 0;
		mbstowcs_s(&convertedChars, wc, cSize, c, _TRUNCATE);

		return wc;
	}

	char* wCharToChar(const wchar_t* wc)
	{
		size_t outputSize = wcslen(wc) + 1; // +1 for null terminator
		char* outputString = new char[outputSize];
		size_t charsConverted = 0;
		wcstombs_s(&charsConverted, outputString, outputSize, wc, wcslen(wc));

		return outputString;
	}

	bool existsFile(const std::wstring& path)
	{
		struct stat buffer;
		std::string charString(wCharToChar(path.c_str()));
		return (stat(charString.c_str(), &buffer) == 0);
	}

	path getModulePath()
	{
		wchar_t szModule[MAX_PATH];
		GetModuleFileName(::g_hInst, szModule, ARRAYSIZE(szModule));
		return szModule;
	}


	path getCrossCloudSettingsPath()
	{
		wchar_t thepath[256];
		SHGetFolderPath(0, CSIDL_LOCAL_APPDATA, NULL, SHGFP_TYPE_CURRENT, thepath);
		return path(thepath) / path(L"CrossCloud") / path(L"CrossCloud") / path(L"1.0");
	}


	path getCrossCloudProgramPath()
	{
		// read the registry value here

		wchar_t thepath[256];
		SHGetFolderPath(0, CSIDL_PROGRAM_FILES, NULL, SHGFP_TYPE_CURRENT, thepath);

		return path(thepath) / path(L"CrossCloud");
	}

	std::wstring utf8_to_wstring(std::string const& src)
	{
		std::wstring_convert<std::codecvt_utf8<wchar_t>> convert;
		return convert.from_bytes(src);
	}

	std::string wstring_to_utf8(std::wstring const& src)
	{
		std::wstring_convert<std::codecvt_utf8<wchar_t>> convert;
		return convert.to_bytes(src);
	}

	bool path_contains_file(path dir, path file)
	{
		// If dir ends with "/" and isn't the root directory, then the final
		// component returned by iterators will include "." and will interfere
		// with the std::equal check below, so we strip it before proceeding.
		if (dir.filename() == L".")
			dir.remove_filename();
		// We're also not interested in the file's name.
		if(file.has_filename())
			file.remove_filename();

		// If dir has more components than file, then file can't possibly
		// reside in dir.
		auto dir_len = std::distance(dir.begin(), dir.end());
		auto file_len = std::distance(file.begin(), file.end());
		if (dir_len > file_len)
			return false;

		// This stops checking when it reaches dir.end(), so it's OK if file
		// has more directory components afterward. They won't be checked.
		return std::equal(dir.begin(), dir.end(), file.begin());
	}

	bool crossCloudRunning()
	{
		LOG_MESSAGE("Checking if lockfile can be opened exclusivly " << getCrossCloudLockFilePath() << std::endl);
		HANDLE hFile = CreateFile(getCrossCloudLockFilePath().wstring().c_str(), GENERIC_READ | GENERIC_WRITE,
			0, // open with exclusive access
			NULL, // no security attributes
			OPEN_EXISTING, // creating a new temp file
			0, // not overlapped index/O
			NULL);
		
		if (hFile != INVALID_HANDLE_VALUE) //It must fail when CrossCloud has opened the file
		{
			LOG_MESSAGE("INVALID_HANDLE_VALUE -> there is no file" << std::endl);
			CloseHandle(hFile);
			return false;
		}

		if (GetLastError() == ERROR_SHARING_VIOLATION) //means it is already opened by CrossCloud
		{
			LOG_MESSAGE("ERROR_SHARING_VIOLATION -> CC is running" << std::endl);
			CloseHandle(hFile);
			return true;
		}

		LOG_MESSAGE("unknown error " << GetLastError() << std::endl);
		CloseHandle(hFile);
		return false;
	}


	path getCrossCloudLockFilePath()
	{
		return getCrossCloudSettingsPath() / path(L"crosscloud.lock");
	}


}
}
