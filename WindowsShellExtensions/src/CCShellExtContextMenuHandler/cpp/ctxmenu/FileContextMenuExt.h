/**
* (C) 2016 CrossCloud GmbH
*/

#ifndef FILE_CONTEXT_MENU_EXT_H
#define FILE_CONTEXT_MENU_EXT_H

#include "config.h"

#include <map>
#include <vector>
#include <filesystem>

// For IShellExtInit and IContextMenu
#include <shlobj.h>     

#include "utils/IUnknownRefCtr.h"

#include "config.h"
#include "Ipc.h"

namespace cc{
	namespace ipc{
		class Ipc;
	}
}

class CGdiPlusBitmapResource;

namespace Gdiplus
{
	class Bitmap;
}

class FileContextMenuImpl : public IShellExtInit, public IContextMenu
{
public:
	IFACEMETHODIMP QueryInterface(REFIID riid, void **ppv);

    // IShellExtInit
    IFACEMETHODIMP Initialize(LPCITEMIDLIST pidlFolder, LPDATAOBJECT pDataObj, HKEY hKeyProgID);

    // IContextMenu
    IFACEMETHODIMP QueryContextMenu(HMENU hMenu, UINT indexMenu, UINT idCmdFirst, UINT idCmdLast, UINT uFlags);
    IFACEMETHODIMP InvokeCommand(LPCMINVOKECOMMANDINFO pici);
    IFACEMETHODIMP GetCommandString(UINT_PTR idCommand, UINT uFlags, UINT *pwReserved, LPSTR pszName, UINT cchMax);
	
	FileContextMenuImpl();

	void addToCommandMap(UINT commandID, std::wstring command);
	std::wstring getFromCommandMap(UINT commandID);

protected:
    ~FileContextMenuImpl(void);

private:
    // The name of the selected file.
	wchar_t m_szSelectedFile[MAX_PATH];

	// The name of the selected file.
	wchar_t m_dummyText[MAX_PATH];

    // The method that handles the "display" verb.
	void sendAction(HWND hWnd, UINT commandId);

    PWSTR m_pszMenuText;
    HBITMAP m_hMenuBmp;
    PCSTR m_pszVerb;
    PCWSTR m_pwszVerb;
    PCSTR m_pszVerbCanonicalName;
    PCWSTR m_pwszVerbCanonicalName;
    PCSTR m_pszVerbHelpText;
    PCWSTR m_pwszVerbHelpText;

	std::map<UINT, std::wstring> command_map_;

	// marked items
	std::vector<cc::path> selected_items_;

	//class to communicate with crosscloud
	cc::ipc::Ipc ipc_;

	// loading pngs via gdiplus
	//Gdiplus::Bitmap* m_gdiIcon;
	CGdiPlusBitmapResource* m_gdi_resource;
	ULONG_PTR m_gdiplusToken;
};

typedef cc::utils::IUnknownRefCtr<FileContextMenuImpl> FileContextMenuExt;

#endif //FILE_CONTEXT_MENU_EXT_H