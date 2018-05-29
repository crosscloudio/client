//
//  IPCSyncCore.swift
//  CrossCloud
//
//  Created by Christoph Hechenblaikner on 15/10/2016.
//  Copyright © 2016 CrossCloud GmbH. All rights reserved.
//

import Foundation

// structure for holding menuitems coming from the core
public struct MenuItem
{
    // name of the menu entry display in context menu
    var name: String
    // determinse if the menu entry should be disabled (greyed out etc.)
    var enabled: Bool
    // actionId to pass back to the core if item is clicked
    var actionId: String
    // children menu items if OS supports subgrouping (macOS does not)
    var children: [MenuItem]
    // boolean indicating that the item shall be checked. 3 states (nil = don't care, false tick but not ticked, true tick)
    var checked: Bool?
}

// structure for holding PathUpdate infos
public struct PathUpdate
{
    // the path of the item an update is available for
    var path:String
    
    // the status if the item described by path
    var status: String
}

public protocol IPCCore
{
    func getSyncDirectory() -> String?
    func getContextMenu(selectedPaths: Array<String>) -> Array<MenuItem>?
    func performAction(actionId: String, selectedPaths: Array<String>)
    func getPathStatus(path: String) -> String?
    func getPathStatusUpdates() -> [PathUpdate]?
}

class IPCSyncCore: IPCCore
{
    // application group id
    static let APPLICATION_GROUP_ID = "crosscloud.shellextension"
    
    // unix domain socket name (file)
    static let UNIX_DOMAIN_SOCKET_NAME = "unix_socket"
    
    // path to the unix socket
    let coreSocketPath: String
    
    // the unix domain socket connection to the core (nil if not available)
    var coreSocketConnection: FileHandle?
    
    // indicates if the sync core service is available to talk to
    var coreAvailable: Bool = false
    
    /**
     Constructor
     **/
    init(unixSocketPath: String)
    {
        // setting path
        self.coreSocketPath = unixSocketPath
        
        // initializing available flag
        self.coreAvailable = false
    }
    
    /**
     Initialize the underlying socket connection.
     **/
    func connect() -> Bool
    {
        print("connecting to \(self.coreSocketPath)")
        
        // getting unix socket file descriptor
        var coreFD:CInt = 0
        coreFD = openUnixSocketToCore(self.coreSocketPath)
        
        // setting up connection dependent on fd success
        if coreFD > 0
        {
            print("Opened Unix Socket to core. FD: \(coreFD)")
            
            // creating handler for socket file descriptor
            self.coreSocketConnection = FileHandle(fileDescriptor: coreFD)
            
            //indicating that core is available
            self.coreAvailable = true
            
            // indicating success
            return true
        }
        else
        {
            // core appears to be offline or not running
            self.coreAvailable = false
            
            //resetting connection
            self.coreSocketConnection = nil
            
            //indicating failure
            return false
        }
    }
    
    /**
     gets the currently configured syn directory from the core
     **/
    func getSyncDirectory() -> String?
    {
        print("getting sync directory")
        
        // crating request
        if let request = self.buildJSONRequest(methodName: "get_sync_directory", params: nil)
        {
            // execute
            let result = self.executeJSONRequest(requestData: request)
            
            // parsing result
            return result as? String
        }
        
        return nil
    }
    
    
    /**
     Obtains the status for a single path from the sync core
     **/
    func getPathStatus(path: String) -> String?
    {
        // sending reuqest to core and returning string result
        if let request = self.buildJSONRequest(methodName: "get_path_status", params: [path]), let result = self.executeJSONRequest(requestData: request)
        {
            return result as? String
        }
        
        return nil
    }
    
    /**
     Pulls for updates in the sync status of items
     **/
    func getPathStatusUpdates() -> [PathUpdate]?
    {
        print("getPathStatusUpdates")
        
        // sending reuqest to core and returning string result
        if let request = self.buildJSONRequest(methodName: "get_status_updates", params: nil), let result = self.executeJSONRequest(requestData: request), let resultArray = result as? [[String: String]]
        {
            // creating results of this call
            var statusUpdate = [PathUpdate]()
            
            // iterating over results and mapping to PathUpdates
            for update in resultArray
            {
                if let path = update["path"], let status = update["status"]
                {
                    statusUpdate.append(PathUpdate(path: path, status: status))
                }
            }
            
            // returning results
            return statusUpdate
        }
        
        return nil
    }
    
    
    /**
     returns a context menu for the selected path as nested MenuItem objects
     **/
    func getContextMenu(selectedPaths: Array<String>) -> [MenuItem]?
    {
        print("getting context menu")
        
        // executing
        if let request =  self.buildJSONRequest(methodName: "get_context_menu", params: [selectedPaths]), let contextMenu = self.executeJSONRequest(requestData: request) as? [[String: Any]]
        {
            // parsing context menu into result
            return self.parseContextMenu(contextMenu: contextMenu)
        }
        else
        {
            // no menu items
            return nil
        }
    }
    
    /**
     send a perform action to the core idefitied by actionid
     **/
    func performAction(actionId: String, selectedPaths: Array<String>)
    {
        print("performing action")
        
        // creating request
        if let request =  self.buildJSONRequest(methodName: "perform_action", params: [actionId, selectedPaths])
        {
            // executing
            _ = self.executeJSONRequest(requestData: request)
        }
    }
    
    
    /**
     builds a JSON RPC request using the given method name and parameters,
     returns nil if request cannot be gererated or data representing the request (utf8)
     **/
    func buildJSONRequest(methodName: String, params: [Any]?, callAsync: Bool = false) -> Data?
    {
        return autoreleasepool{() -> Data? in
            // building basic request
            var request = ["jsonrpc": "2.0", "method": methodName] as [String : Any]
            
            // if not an async call (=notification) -> adding call id
            if !callAsync
            {
                request["id"] = 1
            }
            
            // setting params in request if present
            if params != nil
            {
                request["params"] = params
            }
            
            do
            {
                // returning finished request
                return try JSONSerialization.data(withJSONObject: request)
            }
            catch
            {
                return nil
            }
        }
    }
    
    /**
     Executes a JSON RPC request (passed as data) and returns the result
     **/
    func executeJSONRequest(requestData: Data, callAsync: Bool = false) -> Any?
    {
        // executing json request in own release pool -> this is needed as filehandle.read allocates memory with malloc/realloc and frees it internally
        // but memory is not cleaned up by os until needed (app heap size reaches critical size). We don't want this as the extension RAM size increses to a few
        // hundret MBs -> threrefore this forces cleanup after execution and memory stays low
        return autoreleasepool { () -> Any? in
            
            if self.coreAvailable == false
            {
                if self.connect() == false
                {
                    return nil
                }
            }
            
            do
            {
                // writing size of message to channel (4 bytes!), note that count is size of data in bytes!!
                var messageSize = UInt32(requestData.count)
                print("--> size: \(messageSize)")
                
                try ObjC.catchException(
                    {
                        self.coreSocketConnection?.write(Data(bytes: &messageSize, count:4))
                        
                        //sending request to core
                        self.coreSocketConnection?.write(requestData)
                })
                
                print("--> \(requestData.count)")
                print("--> \(String(describing: String(data: requestData, encoding: String.Encoding.utf8)))")
                
                if callAsync
                {
                    return nil
                }
                
                // reading response size
                if let sizeResponseData = self.coreSocketConnection?.readData(ofLength: 4)
                {
                    // parsing response size
                    var responseSize: Int = 0
                    (sizeResponseData as NSData).getBytes(&responseSize, length: 4)
                    
                    //reading response of determined size
                    if let responseData = self.coreSocketConnection?.readData(ofLength: responseSize)
                    {
                        print("<-- \(responseData.count)")
                        print("--> \(String(describing: String(data: responseData, encoding: String.Encoding.utf8)))")
                        
                        //parsing response
                        if let jsonResponse = try JSONSerialization.jsonObject(with: responseData) as? [String: Any]
                        {
                            let response = jsonResponse["result"]
                            
                            // returning parsed response
                            return response
                        }
                    }
                }
                else
                {
                    // could not read data size and therefore not data
                    return nil
                }
            }
            catch
            {
                print("Error executing request")
                self.coreAvailable = false
            }
            
            return nil
        }
    }
    
    /**
     Parses a complete context menu of menuItems
     **/
    func parseContextMenu(contextMenu: [[String : Any]]) -> [MenuItem]
    {
        // array for resulting menuItems
        var resultingMenuItems = [MenuItem]()
        
        // iterating over menu items and parsing recursively
        for item in contextMenu
        {
            if let newItem = jsonToMenuItem(jsonMenuItem: item)
            {
                // parsing and adding to result
                resultingMenuItems.append(newItem)
            }
        }
        
        // returning list of menuItems (now containing menuItems as children if present)
        return resultingMenuItems
    }
    
    /**
     Translates a json menu item into a menuItem struct object.
     It calls itself recursively until itself and all children are parsed.
     **/
    func jsonToMenuItem(jsonMenuItem: [String: Any]) -> MenuItem?
    {
        // container for children fo current node
        var children = [MenuItem]()
        
        // if item has children -> parsing all chrildren recursively
        if let itemChildren = jsonMenuItem["children"] as? [[String: Any]]
        {
            // iterating over children
            for child in itemChildren
            {
                // getting child items in menuItem form -> !! RECURSIVE !!
                if let childItem = self.jsonToMenuItem(jsonMenuItem: child)
                {
                    // appending new children to child
                    children.append(childItem)
                }
            }
            
            if let name = jsonMenuItem["name"] as? String, let enabled = jsonMenuItem["enabled"] as? Bool, let actionId = jsonMenuItem["actionId"] as? String
            {
                //parsing if optional checked item is set
                var checked: Bool? = nil
                if let value = jsonMenuItem["checked"] as? Bool
                {
                    checked = value
                }
                
                // building menu item
                return MenuItem(name: name, enabled: enabled, actionId: actionId, children: children, checked: checked)
            }
        }
        
        return nil
    }
}
