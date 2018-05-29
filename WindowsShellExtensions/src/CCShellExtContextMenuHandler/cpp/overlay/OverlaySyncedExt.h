/**
* (C) 2016 CrossCloud GmbH
*/

#ifndef OVERLAY_EXT_H
#define OVERLAY_EXT_H

#include "config.h"
#include <shlobj.h>
#include <utils/IUnknownRefCtr.h>
#include <Ipc.h>

namespace cc
{
namespace overlay
{

class OverlaySyncedExtImpl : public IShellIconOverlayIdentifier
{
public:
	virtual ~OverlaySyncedExtImpl();

	OverlaySyncedExtImpl();

	STDMETHODIMP QueryInterface(const IID& riid, void** ppvObject) override;
	STDMETHODIMP IsMemberOf(PCWSTR pwszPath, DWORD dwAttrib) override;
	STDMETHODIMP GetOverlayInfo(PWSTR pwszIconFile, int cchMax, int* pIndex, DWORD* pdwFlags) override;
	STDMETHODIMP GetPriority(int* pIPriority) override;

protected:
	ipc::Ipc ipc_;
};

typedef utils::IUnknownRefCtr<OverlaySyncedExtImpl> OverlaySyncedExt;

}
}



#endif // OVERLAY_EXT_H