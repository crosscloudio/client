/**
* (C) 2016 CrossCloud GmbH
*/


#pragma once
#include "config.h"

#include <unknwn.h>     // For IClassFactory
#include <Shlwapi.h>
#include "utils/IUnknownRefCtr.h"

namespace cc {	namespace utils {

template <typename Impl>  class ClassFactoryImpl : public IClassFactory
{
public:
	// IUnknown
	IFACEMETHODIMP QueryInterface(REFIID riid, void **ppv);
	// IClassFactory
	IFACEMETHODIMP CreateInstance(IUnknown *pUnkOuter, REFIID riid, void **ppv);
	IFACEMETHODIMP LockServer(BOOL fLock);

	ClassFactoryImpl();

protected:
	virtual ~ClassFactoryImpl();

private:
	long m_cRef;
};

template <typename T>
using ClassFactory = IUnknownRefCtr<ClassFactoryImpl<typename T>>;

extern long ::g_cDllRef;

template <typename Impl>
IFACEMETHODIMP ClassFactoryImpl<Impl>::QueryInterface(REFIID riid, void **ppv)
{
	static const QITAB qit[] =
	{
		QITABENT(ClassFactoryImpl, IClassFactory),
		{ 0 },
	};
	return QISearch(this, qit, riid, ppv);
}

//
// IClassFactory
//

template <class Impl>
IFACEMETHODIMP ClassFactoryImpl<Impl>::CreateInstance(IUnknown *pUnkOuter, REFIID riid, void **ppv)
{
	HRESULT hr = CLASS_E_NOAGGREGATION;

	// pUnkOuter is used for aggregation. We do not support it in the sample.
	if (pUnkOuter == NULL)
	{
		hr = E_OUTOFMEMORY;

		// Create the COM component.
		Impl *pExt = new (std::nothrow) Impl();
		if (pExt)
		{
			// Query the specified interface.
			hr = pExt->QueryInterface(riid, ppv);
			pExt->Release();
		}
	}

	return hr;
}


template <typename Impl>
ClassFactoryImpl<Impl>::ClassFactoryImpl() : m_cRef(1)
{
	InterlockedIncrement(&g_cDllRef);
}


template <typename Impl>
ClassFactoryImpl<Impl>::~ClassFactoryImpl()
{
	InterlockedDecrement(&g_cDllRef);
}


template <typename Impl>
IFACEMETHODIMP ClassFactoryImpl<Impl>::LockServer(BOOL fLock)
{
	if (fLock)
	{
		InterlockedIncrement(&g_cDllRef);
	}
	else
	{
		InterlockedDecrement(&g_cDllRef);
	}
	return S_OK;
}


}
}


