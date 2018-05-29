//
//  IPCHelper.swift
//  CrossCloud
//
//  Created by Christoph Hechenblaikner on 18/10/2016.
//  Copyright © 2016 CrossCloud GmbH. All rights reserved.
//

import Cocoa


class IPCHelper: NSObject {
    
    //this method extracts all menuItems from menuItems
    static func extractAllChildrenRecusively(menuItem: MenuItem) -> [MenuItem]
    {
        return extractAllChildrenRecursivelyWithGuard(menuItem: menuItem, recursionLevelMax: 10, recursionLevel: 0);
    }
    
    //this is the recursion function called -> it makes sure the recursion does not exceed a defined value since this recursion is input-data dependent
    //and would cause the extension to get stuck in an endless recusion if the provider of data constructs cyclic dependendies of MenuItems
    static func extractAllChildrenRecursivelyWithGuard(menuItem: MenuItem, recursionLevelMax: Int, recursionLevel: Int) -> [MenuItem]
    {
        //defining result of this recursion
        var resultingChildren = [MenuItem]()
        
        //checking recursion level
        if(recursionLevel > recursionLevelMax)
        {
            return resultingChildren
        }
        
        //getting children of item
        for child in menuItem.children
        {
            if(child.children.count > 0)
            {
                //calling recursively
                resultingChildren.append(contentsOf: extractAllChildrenRecursivelyWithGuard(menuItem: child, recursionLevelMax: recursionLevelMax, recursionLevel: recursionLevel + 1))
            }
            else
            {
                //no children, adding self
                resultingChildren.append(child)
            }
        }
        
        return resultingChildren
    }    
}
