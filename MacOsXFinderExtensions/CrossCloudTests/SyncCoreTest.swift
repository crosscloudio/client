//
//  SyncCoreTest.swift
//  CrossCloud
//
//  Created by Christoph Hechenblaikner on 27/10/2016.
//  Copyright © 2016 Johannes Innerbichler. All rights reserved.
//

import XCTest
@testable import CrossCloud_Extension

class SyncCoreTest: XCTestCase {
    
    override func setUp() {
        super.setUp()
        // Put setup code here. This method is called before the invocation of each test method in the class.
    }
    
    override func tearDown() {
        // Put teardown code here. This method is called after the invocation of each test method in the class.
        super.tearDown()
    }
    
    func testGenerateJsonRequestParams() throws
    {
        // creating ipc object
        let ipcCore = IPCSyncCore(unixSocketPath: "")
        
        // test parameters
        let method = "test_method"
        
        let params_int = [1, 2, 3, 4, 5]
        let params_string = ["1", "2", "3", "4", "5"]
        let param_boolean = [true, false, true, true, false]
        
        //int
        // generating json request
        var requestData = ipcCore.buildJSONRequest(methodName: method, params: params_int)
        assert(requestData != nil)
        
        // parsing json request
        var requestJson = try JSONSerialization.jsonObject(with: requestData!) as! [String: Any]
        
        // checking request
        assert(requestJson["jsonrpc"] as? String == "2.0")
        assert(requestJson["method"] as? String == method)
        assert(requestJson["id"] as? Int == 1)
        assert((requestJson["params"] as? [Int])! == params_int)
        
        //string
        // generating json request
        requestData = ipcCore.buildJSONRequest(methodName: method, params: params_string)
        assert(requestData != nil)
        
        // parsing json request
        requestJson = try JSONSerialization.jsonObject(with: requestData!) as! [String: Any]
        
        // checking request
        assert(requestJson["jsonrpc"] as? String == "2.0")
        assert(requestJson["method"] as? String == method)
        assert(requestJson["id"] as? Int == 1)
        assert((requestJson["params"] as? [String])! == params_string)
        
        //boolean
        // generating json request
        requestData = ipcCore.buildJSONRequest(methodName: method, params: param_boolean)
        assert(requestData != nil)
        
        // parsing json request
        requestJson = try JSONSerialization.jsonObject(with: requestData!) as! [String: Any]
        
        // checking request
        assert(requestJson["jsonrpc"] as? String == "2.0")
        assert(requestJson["method"] as? String == method)
        assert(requestJson["id"] as? Int == 1)
        assert((requestJson["params"] as? [Bool])! == param_boolean)
        
        
        //no parametes
        // generating json request
        requestData = ipcCore.buildJSONRequest(methodName: method, params: nil)
        assert(requestData != nil)
        
        // parsing json request
        requestJson = try JSONSerialization.jsonObject(with: requestData!) as! [String: Any]
        
        // checking request
        assert(requestJson["jsonrpc"] as? String == "2.0")
        assert(requestJson["method"] as? String == method)
        assert(requestJson["id"] as? Int == 1)
        assert(requestJson["params"] == nil)
    }
    
    func testGenerateJsonRequestSpecialCharacters() throws
    {
        let methodNameSpecialCharacters = "äääüüüßßß12344"
        
        // creating ipc object
        let ipcCore = IPCSyncCore(unixSocketPath: "")
        
        // generating json request
        let requestData = ipcCore.buildJSONRequest(methodName: methodNameSpecialCharacters, params: nil)
        assert(requestData != nil)
        
        // parsing json request
        let requestJson = try JSONSerialization.jsonObject(with: requestData!) as! [String: Any]
        
        // checking request
        assert(requestJson["method"] as? String == methodNameSpecialCharacters)
    }
    
    
    func testExecuteAsync() throws
    {
        // creating ipc object
        let ipcCore = IPCSyncCore(unixSocketPath: "")
        
        // setting available internally to true -> so we can send without connecting
        ipcCore.coreAvailable = true
        
        // creating dummy handler for tests
        let dummySocket = URL(fileURLWithPath: NSTemporaryDirectory()).appendingPathComponent("test_dummy_socket")
        FileManager.default.createFile(atPath: (dummySocket.path), contents: nil)
        let myDummyFileHandler = try FileHandle(forUpdating: dummySocket)
        ipcCore.coreSocketConnection = myDummyFileHandler
        
        //executing getSyncDir
        let method = "my_test_method"
        let params = [1,2,3]
        let request = ipcCore.buildJSONRequest(methodName: method, params: params, callAsync: true)
        _ = ipcCore.executeJSONRequest(requestData: request!, callAsync: true)
        
        //let result = try String(contentsOfFile: (dummySocket?.path)!, encoding: String.Encoding.utf8)
        
        // reading written data
        var resultData = try Data(contentsOf: dummySocket)
        
        // extracting size from data
        var requestSize: Int = 0
        (resultData as NSData).getBytes(&requestSize, length: 4)
        resultData.removeFirst(4)
        
        // parsing json request
        let resultJson = try JSONSerialization.jsonObject(with: resultData) as! [String: Any]
        
        // checking request
        assert(resultJson["jsonrpc"] as? String == "2.0")
        assert(resultJson["method"] as? String == method)
        assert(resultJson["id"] == nil)
        assert((resultJson["params"] as! [Int]) == params)
        
        // deleting file
        try FileManager.default.removeItem(at: dummySocket)
    }
    
    func testJsonToMenuItem()
    {
        // creating ipc object
        let ipcCore = IPCSyncCore(unixSocketPath: "")
        
        // creating json menuitem represenation
        let testName = "testymctestface"
        let testActionId = "pushthebutton"
        var menuitem = [String: Any]()
        menuitem["name"] = testName
        menuitem["enabled"] = false
        menuitem["actionId"] = testActionId
        
        // creating child json represenation
        var child = [String: Any]()
        child["name"] = testName
        child["enabled"] = true
        child["actionId"] = testActionId
        child["children"] = []
        
        menuitem["children"] = [child]
        
        let result = ipcCore.jsonToMenuItem(jsonMenuItem: menuitem)
        assert(result?.name == testName)
        assert(result?.actionId == testActionId)
        assert(result?.enabled == false)
        assert(result?.children.count == 1)
        
        let resultChild = result?.children[0]
        assert(resultChild?.name == testName)
        assert(resultChild?.actionId == testActionId)
        assert(resultChild?.enabled == true)
        assert(resultChild!.children.count == 0)
    }
    
    func testextractAllChildrenRecusively()
    {
        // generating menuitem with hirarchical structure
        let testMenuItem = setUpHirarchicalTestMenuItems()[0]
        
        // extracting all items recursively
        let extractedItems = IPCHelper.extractAllChildrenRecusively(menuItem: testMenuItem)
        
        // 20 items as children of root, each has 20 children, all items with children are not returned
        assert(extractedItems.count == 400)
        
        // test that original top item is not in list
        assert(extractedItems.contains(where: { (item) -> Bool in
            return item.name == testMenuItem.name && item.actionId == testMenuItem.actionId
        }) == false)
        
        // test that non of the extracted items has children
        for extractedItem in extractedItems
        {
            assert(extractedItem.children.count == 0)
        }
    }
    
    func testParseContextMenu()
    {
        // creating ipc object
        let ipcCore = IPCSyncCore(unixSocketPath: "")
        
        // creating json menuitem represenation
        let testName = "testymctestface"
        let testActionId = "pushthebutton"
        var menuitem = [String: Any]()
        menuitem["name"] = testName
        menuitem["enabled"] = false
        menuitem["actionId"] = testActionId
        
        // creating child json represenation
        var child = [String: Any]()
        child["name"] = testName
        child["enabled"] = true
        child["actionId"] = testActionId
        child["children"] = []
        
        menuitem["children"] = [child]
        
        let parsedMenu = ipcCore.parseContextMenu(contextMenu: [menuitem, menuitem])
        assert(parsedMenu.count == 2)
        
        for parsedMenuItem in parsedMenu
        {
            assert(parsedMenuItem.name == testName)
            assert(parsedMenuItem.actionId == testActionId)
            assert(parsedMenuItem.enabled == false)
            assert(parsedMenuItem.children.count == 1)
            
            for parsedChild in parsedMenuItem.children
            {
                assert(parsedChild.name == testName)
                assert(parsedChild.actionId == testActionId)
                assert(parsedChild.enabled == true)
                assert(parsedChild.children.count == 0)
            }
        }
    }
    
    /** 
     helper method setting up a menuItem structure of 3 levels: 
     20 top level
     20 in each child of top level
     20 in each child of second level
     **/
    func setUpHirarchicalTestMenuItems() -> [MenuItem]
    {
        // creating children level 2
        var child_items_2 = [MenuItem]()
        for index in 1...20
        {
            // creating children first level
            let child_item = MenuItem(name: "item_child_2_\(index)", enabled: false, actionId: "action_child_2\(index)", children: [])
            child_items_2.append(child_item)
        }
        
        // creating children level 1
        var child_items_1 = [MenuItem]()
        for index in 1...20
        {
            // creating children first level
            let child_item = MenuItem(name: "item_child_1_\(index)", enabled: false, actionId: "action_child_1\(index)", children: child_items_2)
            child_items_1.append(child_item)
        }
        
        // creating top level items where every second one has children
        var items: [MenuItem] = [MenuItem]()
        for index in 1...20
        {
            // creating top level item
            let item = MenuItem(name: "item_top_\(index)", enabled: true, actionId: "action_top_\(index)", children: child_items_1)
            items.append(item)
        }
        
        return items
    }
}
