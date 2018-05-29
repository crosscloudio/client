/**
* (C) 2016 CrossCloud GmbH
*/

#include "FileContextMenuExt.h"
#include "config.h"

#include <strsafe.h>
#include <Shlwapi.h>
#include "utils/logging.h"

#include "utils/utils.h"
#include <fstream>
#include <sstream>
#include <string>
#include <codecvt>
#include <gdiplus.h>
#include <shellapi.h>
#include "utils/CGdiPlusBitmap.h"


extern HINSTANCE g_hInst;
extern long g_cDllRef;

#define IDM_DISPLAY             0  // The command's identifier offset


FileContextMenuImpl::FileContextMenuImpl(void) :
	m_pszMenuText(L"&CrossCloud"),
	m_pszVerb("cppdisplay"),
	m_pwszVerb(L"cppdisplay"),
	m_pszVerbCanonicalName("CrossCloud"),
	m_pwszVerbCanonicalName(L"CrossCloud"),
	m_pszVerbHelpText("CrossCloud"),
	m_pwszVerbHelpText(L"CrossCloud")
{
	InterlockedIncrement(&g_cDllRef);

	LOG_FUN_ENTRY;

	// initialize winsock
	WORD version(MAKEWORD(2, 2));
	WSAData data = {0};

	WSAStartup(version, &data);

	// Load the icon for the context menu

	Gdiplus::GdiplusStartupInput gdiplusStartupInput;
	Gdiplus::GdiplusStartup(&m_gdiplusToken, &gdiplusStartupInput, nullptr);

	Gdiplus::Color col;

	//CGdiPlusBitmapResource cgd;
	m_gdi_resource = new CGdiPlusBitmapResource();

	if (!m_gdi_resource->Load(102, RT_RCDATA, g_hInst))
	{
		LOG_MESSAGE("Problem loading icon from resource" << std::endl);
	}
	else
	{
		LOG_MESSAGE("ctor Icon heigh: " << m_gdi_resource->m_pBitmap->GetHeight() << std::endl);
		m_gdi_resource->m_pBitmap->GetHBITMAP(col, &m_hMenuBmp);
	}

	//IStream* pStream = NULL;
	//::CreateStreamOnHGlobal(NULL, FALSE, &pStream);
	//m_gdiIcon = Gdiplus::Bitmap::FromStream(pStream);
	//pStream->Release();

	//::ReleaseGlo
	//auto icon_path = cc::utils::getCrossCloudProgramPath() / cc::path(L"/app/data/winSwt/icon_blk_16_none.png");
	//m_gdiIcon = new Gdiplus::Bitmap(icon_path.string().c_str());
}

IFACEMETHODIMP FileContextMenuImpl::QueryInterface(REFIID riid, void** ppv)
{
	static const QITAB qit[] =
	{
		QITABENT(FileContextMenuImpl, IContextMenu),
		QITABENT(FileContextMenuImpl, IShellExtInit),
		{0},
	};
	HRESULT hr = QISearch(this, qit, riid, ppv);
	return hr;
}


FileContextMenuImpl::~FileContextMenuImpl(void)
{
	LOG_FUN_ENTRY;
	if (m_hMenuBmp)
	{
		DeleteObject(m_hMenuBmp);
		m_hMenuBmp = NULL;
	}

	if (m_gdi_resource)
	{
		delete m_gdi_resource;
	}

	Gdiplus::GdiplusShutdown(m_gdiplusToken);

	InterlockedDecrement(&g_cDllRef);

	LOG_MESSAGE("~FileContextMenuImpl END" << std::endl);
}


void FileContextMenuImpl::sendAction(HWND hWnd, UINT commandId)
{
	LOG_FUN_ENTRY;
	try
	{
		LOG_MESSAGE(L"Exec : " << commandId << std::endl);
		auto command = command_map_.at(commandId);
		ipc_.PerformAction(command, selected_items_);
	}
	catch (std::out_of_range& ex)
	{
		LOG_MESSAGE(L"Filed Exec : no action " << commandId << L" exc" << ex.what() << std::endl);
	}


	//command_map_.at(commandId)
	//   wchar_t szMessage[300];
	//   if (SUCCEEDED(StringCchPrintf(szMessage, ARRAYSIZE(szMessage), 
	//	L"The selected file is:\r\n\r\n%s\r\n\r\n%s id=%i", this->m_szSelectedFile, cc::utils::charToWChar(getFromCommandMap(commandId).c_str()), commandId)))
	//   {
	//       MessageBox(hWnd, szMessage, L"CppShellExtContextMenuHandler", MB_OK);
	//}

	//	ActionExecutor::executeActionHandler(_selectedPaths, getFromCommandMap(commandId));
}


#pragma region IShellExtInit

/**
 * This intitalize the extension. In case of the context menu extension, this is called everytime 
 * the context menu is loaded. Also the Selected items can be queried here.
*/
IFACEMETHODIMP FileContextMenuImpl::Initialize(
	LPCITEMIDLIST pidlFolder, LPDATAOBJECT pDataObj, HKEY hKeyProgID)
{
	LOG_FUN_ENTRY;
	if (NULL == pDataObj)
	{
		LOG_FUN_RETURN(E_INVALIDARG);
	}

	HRESULT hr = E_FAIL;

	// check if crosscloud is running
	//if (!cc::utils::crossCloudRunning()) {
	//	LOG_MESSAGE("CrossCloud is not Running" << std::endl);
	//	LOG_FUN_RETURN(E_FAIL);
	//}

	try
	{
		//try to connect ipc interface
		ipc_.Connect();
	}
	catch (cc::ipc::IpcException ex)
	{
		LOG_MESSAGE("Can't connect ipc" << std::endl);
		LOG_MESSAGE(ex.what() << std::endl);
		LOG_FUN_RETURN(E_FAIL);
	}

	cc::path cc_sync_path = ipc_.GetSyncDirectory();

	FORMATETC fe = {CF_HDROP, NULL, DVASPECT_CONTENT, -1, TYMED_HGLOBAL};
	STGMEDIUM stm;

	// The pDataObj pointer contains the objects being acted upon. In this 
	// example, we get an HDROP handle for enumerating the selected files and 
	// folders.
	if (SUCCEEDED(pDataObj->GetData(&fe, &stm)))
	{
		// Get an HDROP handle.
		HDROP hDrop = static_cast<HDROP>(GlobalLock(stm.hGlobal));
		if (hDrop != NULL)
		{
			// clear list
			selected_items_.clear();

			// Determine how many files are involved in this operation. This 
			// code sample displays the custom context menu item when only 
			// one file is selected. 
			UINT nFiles = DragQueryFile(hDrop, 0xFFFFFFFF, NULL, 0);

			for (UINT fileIter = 0; fileIter < nFiles; ++fileIter)
			{
				wchar_t selectedFile[MAX_PATH];
				// Get the path of the file.
				if (0 != DragQueryFile(hDrop, fileIter, selectedFile,
				                       ARRAYSIZE(selectedFile)))
				{
					//check if the item is a subitem of the cc path
					cc::path selected_file_path(selectedFile);

					if (cc::utils::path_contains_file(cc_sync_path, selected_file_path))
					{
						selected_items_.push_back(selected_file_path);
						hr = S_OK;
					}
					else
					{
						LOG_MESSAGE("Wrong directory :" << selected_file_path << std::endl);
						LOG_MESSAGE("It is not in :" << cc_sync_path << std::endl);
					}
				}
			}
			GlobalUnlock(stm.hGlobal);
		}

		ReleaseStgMedium(&stm);
	}
	// If any value other than S_OK is returned from the method, the context 
	// menu item is not displayed.
	LOG_FUN_RETURN(hr);
}

#pragma endregion

#pragma region IContextMenu

//
//   FUNCTION: FileContextMenuImpl::QueryContextMenu
//
//   PURPOSE: The Shell calls IContextMenu::QueryContextMenu to allow the 
//            context menu handler to add its menu items to the menu. It 
//            passes in the HMENU handle in the hmenu parameter. The 
//            indexMenu parameter is set to the index to be used for the 
//            first menu item that is to be added.
//
IFACEMETHODIMP FileContextMenuImpl::QueryContextMenu(
	HMENU hMenu, UINT indexMenu, UINT idCmdFirst, UINT idCmdLast, UINT uFlags)
{
	LOG_FUN_ENTRY;

	// If uFlags include CMF_DEFAULTONLY then we should not do anything.
	if (CMF_DEFAULTONLY & uFlags)
	{
		return MAKE_HRESULT(SEVERITY_SUCCESS, 0, USHORT(0));
	}

	// if there are no selected items, the menu is meaningless
	if (!selected_items_.size())
		return E_FAIL;

	UINT currentCommandId = idCmdFirst;
	UINT currentMenuIndex = indexMenu;

	for (auto item : ipc_.GetContextMenu(selected_items_))
	{
		MENUITEMINFO mii = {sizeof(mii)};
		mii.dwTypeData = const_cast<LPWSTR>(item.name.c_str());
		item.enabled ? mii.fState = MFS_ENABLED : mii.fState = MFS_DISABLED;
		mii.fMask = MIIM_STRING | MIIM_FTYPE | MIIM_ID | MIIM_STATE;

		mii.fMask |= MIIM_BITMAP;
		mii.hbmpItem = static_cast<HBITMAP>(m_hMenuBmp);


		command_map_.insert(std::make_pair(currentCommandId - idCmdFirst, item.actionId));
		LOG_MESSAGE(item.name << L" : " << currentCommandId - idCmdFirst << std::endl);
		mii.wID = currentCommandId++;

		if (item.children.size())
		{
			mii.fMask |= MIIM_SUBMENU;
			mii.hSubMenu = CreatePopupMenu();
			UINT submenu_index = 0;


			LOG_MESSAGE("CHILDS" << std::endl);
			for (auto subitem : item.children)
			{
				MENUITEMINFO submii = {sizeof(mii)};

				command_map_.insert(std::make_pair(currentCommandId - idCmdFirst, subitem.actionId));
				LOG_MESSAGE(subitem.name << L" : " << currentCommandId - idCmdFirst << std::endl);
				submii.wID = currentCommandId++;

				submii.dwTypeData = const_cast<LPWSTR>(subitem.name.c_str());
				subitem.enabled ? submii.fState = MFS_ENABLED : submii.fState = MFS_DISABLED;

				submii.fMask = MIIM_STRING | MIIM_FTYPE | MIIM_ID | MIIM_STATE;

				// if it is not undifined we want checkmarks
				if (subitem.checked != cc::ipc::MICS_UNDEFINED)
				{
					submii.fMask |= MIIM_CHECKMARKS;

					// set the according state to the checkmarks
					if (subitem.checked == cc::ipc::MICS_CHECKED)
						submii.fState |= MFS_CHECKED;
					else
						submii.fState |= MFS_GRAYED;
				}


				InsertMenuItem(mii.hSubMenu, submenu_index++, TRUE, &submii);
			}
			LOG_MESSAGE("EOC" << std::endl);
		}
		InsertMenuItem(hMenu, currentMenuIndex++, TRUE, &mii);
	}

	LOG_MESSAGE("Done building menu" << std::endl);

	// Return an HRESULT value with the severity set to SEVERITY_SUCCESS. 
	// Set the code value to the offset of the largest command identifier 
	// that was assigned, plus one (1).
	return MAKE_HRESULT(SEVERITY_SUCCESS, 0, currentCommandId - idCmdFirst + 1);

	//return MAKE_HRESULT(SEVERITY_SUCCESS, 0, 1);
}


//
//   FUNCTION: FileContextMenuImpl::InvokeCommand
//
//   PURPOSE: This method is called when a user clicks a menu item to tell 
//            the handler to run the associated command. The lpcmi parameter 
//            points to a structure that contains the needed information.
//
IFACEMETHODIMP FileContextMenuImpl::InvokeCommand(LPCMINVOKECOMMANDINFO pici)
{
	LOG_FUN_ENTRY;
	BOOL fUnicode = FALSE;

	// Determine which structure is being passed in, CMINVOKECOMMANDINFO or 
	// CMINVOKECOMMANDINFOEX based on the cbSize member of lpcmi. Although 
	// the lpcmi parameter is declared in Shlobj.h as a CMINVOKECOMMANDINFO 
	// structure, in practice it often points to a CMINVOKECOMMANDINFOEX 
	// structure. This struct is an extended version of CMINVOKECOMMANDINFO 
	// and has additional members that allow Unicode strings to be passed.
	if (pici->cbSize == sizeof(CMINVOKECOMMANDINFOEX))
	{
		if (pici->fMask & CMIC_MASK_UNICODE)
		{
			fUnicode = TRUE;
		}
	}

	// Determines whether the command is identified by its offset or verb.
	// There are two ways to identify commands:
	// 
	//   1) The command's verb string 
	//   2) The command's identifier offset
	// 
	// If the high-order word of lpcmi->lpVerb (for the ANSI case) or 
	// lpcmi->lpVerbW (for the Unicode case) is nonzero, lpVerb or lpVerbW 
	// holds a verb string. If the high-order word is zero, the command 
	// offset is in the low-order word of lpcmi->lpVerb.

	// For the ANSI case, if the high-order word is not zero, the command's 
	// verb string is in lpcmi->lpVerb. 
	if (!fUnicode && HIWORD(pici->lpVerb))
	{
		// Is the verb supported by this context menu extension?
		if (StrCmpIA(pici->lpVerb, m_pszVerb) == 0)
		{
			sendAction(pici->hwnd, 3333);
		}
		else
		{
			// If the verb is not recognized by the context menu handler, it 
			// must return E_FAIL to allow it to be passed on to the other 
			// context menu handlers that might implement that verb.
			return E_FAIL;
		}
	}

	// For the Unicode case, if the high-order word is not zero, the 
	// command's verb string is in lpcmi->lpVerbW. 
	else if (fUnicode && HIWORD(((CMINVOKECOMMANDINFOEX*)pici)->lpVerbW))
	{
		// Is the verb supported by this context menu extension?
		if (StrCmpIW(((CMINVOKECOMMANDINFOEX*)pici)->lpVerbW, m_pwszVerb) == 0)
		{
			sendAction(pici->hwnd, 4444);
		}
		else
		{
			// If the verb is not recognized by the context menu handler, it 
			// must return E_FAIL to allow it to be passed on to the other 
			// context menu handlers that might implement that verb.
			return E_FAIL;
		}
	}

	// If the command cannot be identified through the verb string, then 
	// check the identifier offset.
	else
	{
		//LOG_MESSAGE(L"VERB: " << *pici->lpVerb << std::endl);
		sendAction(pici->hwnd, LOWORD(pici->lpVerb));
		//// Is the command identifier offset supported by this context menu 
		//// extension?
		//if (LOWORD(pici->lpVerb) == IDM_DISPLAY)
		//{
		//    sendAction(pici->hwnd);
		//}
		//else
		//{
		//    // If the verb is not recognized by the context menu handler, it 
		//    // must return E_FAIL to allow it to be passed on to the other 
		//    // context menu handlers that might implement that verb.
		//    return E_FAIL;
		//}
	}

	return S_OK;
}


//
//   FUNCTION: CFileContextMenuExt::GetCommandString
//
//   PURPOSE: If a user highlights one of the items added by a context menu 
//            handler, the handler's IContextMenu::GetCommandString method is 
//            called to request a Help text string that will be displayed on 
//            the Windows Explorer status bar. This method can also be called 
//            to request the verb string that is assigned to a command. 
//            Either ANSI or Unicode verb strings can be requested. This 
//            example only implements support for the Unicode values of 
//            uFlags, because only those have been used in Windows Explorer 
//            since Windows 2000.
//
IFACEMETHODIMP FileContextMenuImpl::GetCommandString(UINT_PTR idCommand,
                                                     UINT uFlags, UINT* pwReserved, LPSTR pszName, UINT cchMax)
{
	LOG_FUN_ENTRY;
	HRESULT hr = E_INVALIDARG;

	if (idCommand == IDM_DISPLAY)
	{
		switch (uFlags)
		{
		case GCS_HELPTEXTW:
			// Only useful for pre-Vista versions of Windows that have a 
			// Status bar.
			hr = StringCchCopy(reinterpret_cast<PWSTR>(pszName), cchMax,
			                   m_pwszVerbHelpText);
			break;

		case GCS_VERBW:
			// GCS_VERBW is an optional feature that enables a caller to 
			// discover the canonical name for the verb passed in through 
			// idCommand.
			hr = StringCchCopy(reinterpret_cast<PWSTR>(pszName), cchMax,
			                   m_pwszVerbCanonicalName);
			break;

		default:
			hr = S_OK;
		}
	}

	// If the command (idCommand) is not supported by this context menu 
	// extension handler, return E_INVALIDARG.

	return hr;
}

#pragma endregion
