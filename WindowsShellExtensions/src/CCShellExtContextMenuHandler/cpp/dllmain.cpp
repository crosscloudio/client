/**
* (C) 2016 CrossCloud GmbH
*/

#include "utils/logging.h"
#include "overlay/OverlayUnSyncedExt.h"
long        g_cDllRef = 0;

//to be done before windows.h
#include "config.h"

#include <windows.h>

#include "Reg.h"

#include "utils/ClassFactory.h"           // For the class factory
#include "ctxmenu/FileContextMenuExt.h"
#include "overlay/OverlaySyncedExt.h"

// {FD67F358-021E-49D1-933A-D1D50E59F34A} for IContextMenu
// Created by julian r on 1/22/2016
const CLSID CLSID_FileContextMenuExt = 
{ 0xfd67f358, 0x21e, 0x49d1, { 0x93, 0x3a, 0xd1, 0xd5, 0xe, 0x59, 0xf3, 0x4a } };


// {75EC2AF1-C1A5-4CCD-96DC-2BB9FB2FE7F1} for IShellIconOverlayIdentifier
// Created by julian r on 2/1/2016
const CLSID CLSID_OverlaySyncedExt =
{ 0x75ec2af1, 0xc1a5, 0x4ccd, { 0x96, 0xdc, 0x2b, 0xb9, 0xfb, 0x2f, 0xe7, 0xf1 } };

// {C2B9C7C6-A5C1-49FD-9808-F03F2F697F6C}
// // Created by julian r on 2/2/2016
static const GUID CLSID_OverlayUnSyncedExt =
{ 0xc2b9c7c6, 0xa5c1, 0x49fd, { 0x98, 0x8, 0xf0, 0x3f, 0x2f, 0x69, 0x7f, 0x6c } };



HINSTANCE   g_hInst     = NULL;


BOOL APIENTRY DllMain(HMODULE hModule, DWORD dwReason, LPVOID lpReserved)
{
	switch (dwReason)
	{
	case DLL_PROCESS_ATTACH:
        // Hold the instance of this DLL module, we will use it to get the 
        // path of the DLL to register the component.
        g_hInst = hModule;
        DisableThreadLibraryCalls(hModule);
        break;
	case DLL_THREAD_ATTACH:
	case DLL_THREAD_DETACH:
	case DLL_PROCESS_DETACH:
		break;
	}
	return TRUE;
}


//
//   FUNCTION: DllGetClassObject
//
//   PURPOSE: Create the class factory and query to the specific interface.
//
//   PARAMETERS:
//   * rclsid - The CLSID that will associate the correct data and code.
//   * riid - A reference to the identifier of the interface that the caller 
//     is to use to communicate with the class object.
//   * ppv - The address of a pointer variable that receives the interface 
//     pointer requested in riid. Upon successful return, *ppv contains the 
//     requested interface pointer. If an error occurs, the interface pointer 
//     is NULL. 
//
STDAPI DllGetClassObject(REFCLSID rclsid, REFIID riid, void **ppv)
{
    HRESULT hr = CLASS_E_CLASSNOTAVAILABLE;

    if (IsEqualCLSID(CLSID_FileContextMenuExt, rclsid))
    {
		LOG_MESSAGE( "Instantiation FileContextMenuExt" << std::endl);
        hr = E_OUTOFMEMORY;
		cc::utils::ClassFactory<FileContextMenuExt>* pClassFactory =
			new cc::utils::ClassFactory < FileContextMenuExt >;
        if (pClassFactory)
        {
            hr = pClassFactory->QueryInterface(riid, ppv);
            pClassFactory->Release();
        } 
    }
	else if (IsEqualCLSID(CLSID_OverlaySyncedExt, rclsid))
	{
		LOG_MESSAGE("Instantiation OverlaySyncedExt" << std::endl);
		hr = E_OUTOFMEMORY;
		cc::utils::ClassFactory<cc::overlay::OverlaySyncedExt>* pClassFactory =
			new cc::utils::ClassFactory < cc::overlay::OverlaySyncedExt >;
		if (pClassFactory)
		{
			hr = pClassFactory->QueryInterface(riid, ppv);
			pClassFactory->Release();
		}
	}

	else if (IsEqualCLSID(CLSID_OverlayUnSyncedExt, rclsid))
	{
		LOG_MESSAGE("Instantiation OverlayUnSyncedExt" << std::endl);
		hr = E_OUTOFMEMORY;
		cc::utils::ClassFactory<cc::overlay::OverlayUnSyncedExt>* pClassFactory =
			new cc::utils::ClassFactory < cc::overlay::OverlayUnSyncedExt >;
		if (pClassFactory)
		{
			hr = pClassFactory->QueryInterface(riid, ppv);
			pClassFactory->Release();
		}
	}

    return hr;
}


//
//   FUNCTION: DllCanUnloadNow
//
//   PURPOSE: Check if we can unload the component from the memory.
//
//   NOTE: The component can be unloaded from the memory when its reference 
//   count is zero (i.e. nobody is still using the component).
// 
STDAPI DllCanUnloadNow(void)
{
    return g_cDllRef > 0 ? S_FALSE : S_OK;
}


//
//   FUNCTION: DllRegisterServer
//
//   PURPOSE: Register the COM server and the context menu handler.
// 
STDAPI DllRegisterServer(void)
{
    HRESULT hr;

    wchar_t szModule[MAX_PATH];
    if (GetModuleFileName(g_hInst, szModule, ARRAYSIZE(szModule)) == 0)
    {
        hr = HRESULT_FROM_WIN32(GetLastError());
        return hr;
    }

    // Register the components.
    hr = RegisterInprocServer(szModule, CLSID_FileContextMenuExt, 
        L"CrossCloud.FileContextMenuExt Class", 
        L"Apartment");

	if (SUCCEEDED(hr))
	{
		hr = RegisterInprocServer(szModule, CLSID_OverlaySyncedExt,
			L"CrossCloud.OverlaySyncedExt Class",
			L"Apartment");
	}
	else { return hr; }

	if (SUCCEEDED(hr))
	{
		hr = RegisterInprocServer(szModule, CLSID_OverlayUnSyncedExt,
			L"CrossCloud.OverlayUnSyncedExt Class",
			L"Apartment");
	}
	else { return hr; }

    if (SUCCEEDED(hr))
    {
        // Register the context menu handler. The context menu handler is 
        // associated with all directories.
        hr = RegisterShellExtContextMenuHandler(L"Folder", 
            CLSID_FileContextMenuExt, 
            L"CrossCloud.FileContextMenuExt");

	}
	else { return hr; }

	if (SUCCEEDED(hr))
	{
		// Register the context menu handler. The context menu handler is 
		// associated with the * file class.
		hr = RegisterShellExtContextMenuHandler(L"*",
			CLSID_FileContextMenuExt,
			L"CrossCloud.FileContextMenuExt");

	}

	RegisterIconOverlayHandler(std::wstring(L"   CrossCloudSynced"), CLSID_OverlaySyncedExt);
	RegisterIconOverlayHandler(std::wstring(L"   CrossCloudUnsynced"), CLSID_OverlayUnSyncedExt);
    return hr;
}


//
//   FUNCTION: DllUnregisterServer
//
//   PURPOSE: Unregister the COM server and the context menu handler.
// 
STDAPI DllUnregisterServer(void)
{
    HRESULT hr = S_OK;

    wchar_t szModule[MAX_PATH];
    if (GetModuleFileName(g_hInst, szModule, ARRAYSIZE(szModule)) == 0)
    {
        hr = HRESULT_FROM_WIN32(GetLastError());
        return hr;
    }



	hr = UnregisterInprocServer(CLSID_OverlaySyncedExt);

    // Unregister the components.
    hr = UnregisterInprocServer(CLSID_FileContextMenuExt);
    if (SUCCEEDED(hr))
    {
        // Unregister the context menu handler for *
        hr = UnregisterShellExtContextMenuHandler(L"*", 
            CLSID_FileContextMenuExt);

    }

	if (SUCCEEDED(hr))
	{
		// Unregister the context menu handler for Folders
		hr = UnregisterShellExtContextMenuHandler(L"Folder",
			CLSID_FileContextMenuExt);
	}

    return hr;
}