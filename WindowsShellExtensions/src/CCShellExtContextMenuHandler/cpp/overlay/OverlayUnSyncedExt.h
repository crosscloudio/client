#include "OverlaySyncedExt.h"

namespace cc {	namespace overlay {


class OverlayUnSyncedExt : public OverlaySyncedExt
{
	STDMETHODIMP IsMemberOf(PCWSTR pwszPath, DWORD dwAttrib) override;
	STDMETHODIMP GetOverlayInfo(PWSTR pwszIconFile, int cchMax, int* pIndex, DWORD* pdwFlags) override;
};

}
}

