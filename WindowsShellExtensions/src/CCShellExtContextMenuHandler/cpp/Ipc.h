#ifndef CC_IPC_H
#define CC_IPC_H


#include <filesystem>
#include <fstream>
#include <set>
#include <mutex>
#include <json.hpp>
#include "utils/utils.h"

#define CC_IPC_APP_ID "crosscloud.shellextension"

namespace cc
{
	namespace ipc
	{
		enum SyncStatus {
			Syncing,
			Synced,
			Ignore
		};

		struct IpcException : public std::runtime_error {
		public:
			IpcException(char* what) : std::runtime_error(what)
			{}
		
		};

		// check status of the MenuItem (either no check displayed at all, checked or shown but not checked)
		enum MenuItemCheckboxStatus {MICS_CHECKED, MICS_UNCHECKED, MICS_UNDEFINED};

		struct MenuItem {
			std::wstring name;
			bool enabled;
			std::wstring actionId;
			std::vector<MenuItem> children;
            MenuItemCheckboxStatus checked;
		};



		class Ipc
		{
		public:
			Ipc();
			void Connect();
			cc::path GetSyncDirectory();
			std::vector<MenuItem> GetContextMenu(std::vector<path>& paths);
			void PerformAction(std::wstring action_id, std::vector<path>& paths);
			SyncStatus GetPathStatus(path const& file_path);
			
			bool isConnected() const;
			~Ipc();
		private:
			HANDLE _connection;
			std::mutex _call_mutex;
			nlohmann::json function_call(std::string function_name, nlohmann::json& params);
			uint32_t current_calling_id_;
		};
	}
}

#endif // CC_IPC_H