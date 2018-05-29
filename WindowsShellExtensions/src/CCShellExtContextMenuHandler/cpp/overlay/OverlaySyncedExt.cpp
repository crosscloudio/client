#include "OverlaySyncedExt.h"
#include <Shlwapi.h>
#include "utils/logging.h"
#include <utils/utils.h>

extern HMODULE g_hInst;

namespace cc { namespace overlay {


OverlaySyncedExtImpl::~OverlaySyncedExtImpl()
{
}

OverlaySyncedExtImpl::OverlaySyncedExtImpl()
{
	LOG_MESSAGE("OverlaySyncedExtImpl instance: 0x" << std::hex << g_hInst << std::endl);
	LOG_FUN_ENTRY;
	try {
		ipc_.Connect();
	}
	catch (cc::ipc::IpcException)
	{
		LOG_MESSAGE("Can't conntext to crosscloud" << std::endl);
	}
}

HRESULT OverlaySyncedExtImpl::QueryInterface(const IID& riid, void** ppvObject)
{
	LOG_FUN_ENTRY;
	static const QITAB qit[] =
	{
		QITABENT(OverlaySyncedExtImpl, IShellIconOverlayIdentifier),
		{ 0 },
	};
	HRESULT hr = QISearch(this, qit, riid, ppvObject);
	return hr;
}

HRESULT OverlaySyncedExtImpl::IsMemberOf(PCWSTR pwszPath, DWORD dwAttrib)
{
	LOG_FUN_ENTRY;
	ipc::SyncStatus res;
	path path(pwszPath);
	LOG_MESSAGE(path << std::endl);


	try {
		cc::path cc_sync_path = ipc_.GetSyncDirectory(); 
		if (cc_sync_path.empty()) {
			LOG_FUN_RETURN(S_FALSE);
		}

		
		if (cc::utils::path_contains_file(cc_sync_path, path)) {
			LOG_MESSAGE("Member of the cc directory" << path  << " in " << cc_sync_path << std::endl);
		}
		else {
			LOG_MESSAGE("Not member of the cc directory" << std::endl);
			LOG_FUN_RETURN(S_FALSE);
		}

		res = ipc_.GetPathStatus(path);
	}
	catch (std::exception e)
	{
		LOG_MESSAGE("Failed calling: " << e.what() << std::endl);
		LOG_FUN_RETURN(E_FAIL);
	}

	
	if(res == ipc::Synced)
	{
		LOG_FUN_RETURN(S_OK);
	}
	else
	{
		LOG_FUN_RETURN(S_FALSE);
	}

	
}

HRESULT OverlaySyncedExtImpl::GetOverlayInfo(PWSTR pwszIconFile, int cchMax, int* pIndex, DWORD* pdwFlags)
{
	LOG_FUN_ENTRY;
	GetModuleFileName(g_hInst, pwszIconFile, cchMax);

	*pIndex = -100;

	*pdwFlags = ISIOI_ICONFILE | ISIOI_ICONINDEX;

	return S_OK;
}

HRESULT OverlaySyncedExtImpl::GetPriority(int* pIPriority)
{
	LOG_FUN_ENTRY;
	*pIPriority = 99;
	return S_OK;
}
}
}
