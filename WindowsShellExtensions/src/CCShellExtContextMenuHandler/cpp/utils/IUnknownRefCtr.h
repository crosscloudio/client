/**
* (C) 2016 CrossCloud GmbH
*/

#pragma once

#include "config.h"


namespace cc {
namespace utils {

template <class T>

/**
 * Helper class to implemnt the ref counter for com objects
 */
class IUnknownRefCtr : public T
{

public:
	virtual ~IUnknownRefCtr();
	IUnknownRefCtr();

	// IUnknown
	IFACEMETHODIMP_(ULONG) AddRef();
	IFACEMETHODIMP_(ULONG) Release();
private:
	// Reference count of component.
	long m_cRef;
};

template <class T>
IUnknownRefCtr<T>::IUnknownRefCtr() : m_cRef(1)
{

}

// Query to the interface the component supported.
template <class T>
IUnknownRefCtr<T>::~IUnknownRefCtr()
{
}

// Increase the reference count for an interface on an object.
template <class T>
IFACEMETHODIMP_(ULONG) IUnknownRefCtr<T>::AddRef()
{
	return InterlockedIncrement(&m_cRef);
}

// Decrease the reference count for an interface on an object.
template <class T>
IFACEMETHODIMP_(ULONG) IUnknownRefCtr<T>::Release()
{
	ULONG cRef = InterlockedDecrement(&m_cRef);
	if (0 == cRef)
	{
		delete this;
	}

	return cRef;
}

}
}
