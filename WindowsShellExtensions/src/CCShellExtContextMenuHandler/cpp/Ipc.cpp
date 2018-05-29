#include "Ipc.h"

#include "utils/utils.h"
#include <utils/logging.h>
#include "json.hpp"

namespace cc
{
	namespace ipc
	{
		nlohmann::json Ipc::function_call(std::string function_name, nlohmann::json& params)
		{
			if (_connection == INVALID_HANDLE_VALUE)
			{
				LOG_MESSAGE("reconnecting" << std::endl);
				Connect();
			}

			std::lock_guard<std::mutex> call_guard(_call_mutex);
			nlohmann::json request;
			request["jsonrpc"] = "2.0";
			request["method"] = function_name;
			if (params.size())
				request["params"] = params;
			request["id"] = 1;


			std::string request_string = request.dump();
			uint32_t request_size = static_cast<uint32_t>(request_string.length());

			//_connection.clear();
			//LOG_MESSAGE("sending meesage: " << cc::utils::utf8_to_wstring(request_string) << std::endl);

			//needed for the WriteFile function
			DWORD bytes_written;
			BOOL success = WriteFile(_connection, reinterpret_cast<char*>(&request_size), sizeof(uint32_t), &bytes_written, nullptr);
			if (!success)
			{
				_connection = INVALID_HANDLE_VALUE;
				LOG_MESSAGE("request_size/ failed to write: " << GetLastError() << std::endl);
			}


			success = WriteFile(_connection, request_string.c_str(), static_cast<DWORD>(request_string.length()), &bytes_written, nullptr); // << request_string;

			if (!success)
			{
				_connection = INVALID_HANDLE_VALUE;
				LOG_MESSAGE("request_string/ failed to write: " << GetLastError() << std::endl);
			}

			success = FlushFileBuffers(_connection);

			if (!success)
			{
				_connection = INVALID_HANDLE_VALUE;
				LOG_MESSAGE("flush/ failed to write: " << GetLastError() << std::endl);
			}


			uint32_t response_size;
			DWORD bytes_read;
			success = ReadFile(_connection, reinterpret_cast<char*>(&response_size), sizeof(uint32_t), &bytes_read, nullptr);

			if (!success)
			{
				LOG_MESSAGE("response_size/ error reading response" << GetLastError() << std::endl);
				_connection = INVALID_HANDLE_VALUE;
				return nlohmann::json();
			}
			char* response_buffer = new char[response_size + 1];

			// zero termination for strings
			response_buffer[response_size] = 0;

			success = ReadFile(_connection, response_buffer, response_size, &bytes_read, nullptr);


			if (!success)
			{
				_connection = INVALID_HANDLE_VALUE;
				LOG_MESSAGE("received message failed" << GetLastError() << std::endl);
			}


			nlohmann::json response = nlohmann::json::parse(response_buffer);
			delete[] response_buffer;

			if (response.count("result"))
				return response["result"];
			if (response.count("error"))
				throw IpcException("JSON response does contain a 'error' field.");
			throw IpcException("JSON response does not contain a 'result' field.");
		}

		Ipc::Ipc(): _connection(INVALID_HANDLE_VALUE), current_calling_id_(0)
		{
		}

		void Ipc::Connect()
		{
			wchar_t username[512];
			DWORD username_len = sizeof(username);
			if (!GetUserNameW(username, &username_len))
			{
				LOG_MESSAGE("Got Username failed: " << GetLastError() << std::endl);
				return;
			}
			else
			{
				LOG_MESSAGE("Got Username: " << username << std::endl);
			}

			std::wstring pipename(L"\\\\.\\pipe\\" CC_IPC_APP_ID);

			pipename += L"-";
			pipename += username;

			LOG_MESSAGE("Connecting to pipe: " << pipename << std::endl);
			_connection = CreateFileW(pipename.c_str(),
			                          GENERIC_READ | GENERIC_WRITE,
			                          0,
			                          0,
			                          OPEN_EXISTING,
			                          FILE_ATTRIBUTE_NORMAL,
			                          0);
			if (_connection == INVALID_HANDLE_VALUE)
			{
				LOG_MESSAGE("CreateFileW failed: " << GetLastError() << std::endl);
				throw IpcException("Error opening the named pipe");
			}
		}

		path Ipc::GetSyncDirectory()
		{
			try
			{
				nlohmann::json result = function_call("get_sync_directory", nlohmann::json());
				if (!result.is_string())
					return path();

				return path(utils::utf8_to_wstring(result));
			}
			catch (std::exception& ex)
			{
				LOG_MESSAGE("Ipc::GetSyncDirectory failed" << ex.what() << std::endl);
				//return a random path so it is not matched with something in reallive
				return path("xasdfasdfasdfasdfasdfasf\\y\\z");
			}
		}

		void Ipc::PerformAction(std::wstring action_id, std::vector<path>& paths)
		{
			try
			{
				nlohmann::json paths_json;
				nlohmann::json args;

				for (path& p : paths)
				{
					paths_json.push_back(utils::wstring_to_utf8(p));
				}

				args.push_back(utils::wstring_to_utf8(action_id));
				args.push_back(paths_json);

				function_call("perform_action", args);
			}
			catch (std::exception& ex)
			{
				LOG_MESSAGE("Ipc::PerformAction failed" << ex.what() << std::endl);
			}
		}

		Ipc::~Ipc()
		{
			CloseHandle(_connection);
		}

		std::vector<MenuItem> ConvertMenuRecursive(nlohmann::json& menu_items)
		{
			std::vector<MenuItem> menu_item_vector;
			for (nlohmann::json& menu_item : menu_items)
			{
				if (menu_item.count("enabled") && menu_item.count("name") && menu_item.count("actionId") && menu_item.count("children"))
				{
					MenuItem mi;
					mi.enabled = menu_item["enabled"];
					mi.name = utils::utf8_to_wstring(menu_item["name"]);
					mi.actionId = utils::utf8_to_wstring(menu_item["actionId"]);
					mi.children = ConvertMenuRecursive(menu_item["children"]);

					// setting checked property
					if(menu_item.count("checked"))
					{
						mi.checked = (bool) menu_item["checked"] ? MICS_CHECKED : MICS_UNCHECKED;
					}
					else
					{
						mi.checked = MICS_UNDEFINED;
					}

					menu_item_vector.push_back(mi);
				}
				else
				{
					LOG_MESSAGE("skipped menuitem" << std::endl);
				}
			}
			return menu_item_vector;
		}

		std::vector<MenuItem> Ipc::GetContextMenu(std::vector<path>& paths)
		{
			try
			{
				nlohmann::json paths_json;
				nlohmann::json args;

				for (path& p : paths)
				{
					paths_json.push_back(utils::wstring_to_utf8(p));
				}
				args.push_back(paths_json);

				nlohmann::json result = function_call("get_context_menu", args);

				std::vector<MenuItem> menu_item_vector = ConvertMenuRecursive(result);


				return menu_item_vector;
			}
			catch (std::exception& ex)
			{
				LOG_MESSAGE("Ipc::GetContextMenu failed" << ex.what() << std::endl);
				return std::vector<MenuItem>();
			}
		}

		SyncStatus Ipc::GetPathStatus(path const& file_path)
		{
			try
			{
				nlohmann::json args;
				args.push_back(utils::wstring_to_utf8(file_path));
				nlohmann::json result = function_call("get_path_status", args);
				std::string status = result.get<std::string>();

				LOG_MESSAGE("get_path_status returned " << utils::utf8_to_wstring(status)  << std::endl);

				if (result == "Syncing")
					return Syncing;
				else if (result == "Synced")
					return Synced;
				else
					return Ignore;
			}
			catch (std::exception& ex)
			{
				LOG_MESSAGE("Ipc::IsPathSyncing failed" << ex.what() << std::endl);
				return Ignore;
			}
		}

		bool Ipc::isConnected() const
		{
			return _connection == INVALID_HANDLE_VALUE;
		}
	}
}
