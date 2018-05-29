#include "OverlayUnSyncedExt.h"
#include <utils/logging.h>
#include <utils/utils.h>

namespace cc { namespace overlay {


HRESULT OverlayUnSyncedExt::IsMemberOf(PCWSTR pwszPath, DWORD dwAttrib)
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
			LOG_MESSAGE("Member of the cc directory" << path << " in " << cc_sync_path << std::endl);
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


	if (res == ipc::Syncing)
	{
		LOG_FUN_RETURN(S_OK);
	}
	else
	{
		LOG_FUN_RETURN(S_FALSE);
	}

}

HRESULT OverlayUnSyncedExt::GetOverlayInfo(PWSTR pwszIconFile, int cchMax, int* pIndex, DWORD* pdwFlags)
{
	LOG_FUN_ENTRY;
	HRESULT hr = OverlaySyncedExt::GetOverlayInfo(pwszIconFile, cchMax, pIndex, pdwFlags);
	*pIndex = -101;
	LOG_FUN_RETURN(hr);
}

} 
}
