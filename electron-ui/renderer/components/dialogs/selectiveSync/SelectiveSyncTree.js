import React, { PropTypes } from 'react';
import Tree from 'antd/lib/tree';
import { isEqual, keyBy, orderBy, uniqWith } from 'lodash';
import CircularProgress from 'material-ui/lib/circular-progress';
import { SECONDARY_COLOR } from '../../../styles/constants';

// don't import default ant tree styles because it adds unnecessary global styles
import './ant-tree-styles.less';

import rpcProxy from '../../../utils/rpcProxy';

const TreeNode = Tree.TreeNode;

const STYLES = {
  loading: {
    position: 'relative',
    display: 'flex',
    width: '100%',
    height: '100%',
    alignItems: 'center',
    justifyContent: 'center',
  },
};

export default class SelectiveSyncTree extends React.Component {
  static propTypes = {
    accountId: PropTypes.string.isRequired,
    defaultExpandedPaths: PropTypes.array.isRequired,
    onSelect: PropTypes.func.isRequired,
    selectedPaths: PropTypes.array.isRequired,
  };

  constructor(props, context) {
    super(props, context);
    this.state = {
      checkedKeys: [],
      treeData: [],
      treeDataByName: {},
    };
  }

  componentDidMount() {
    this.loadRoot();
  }

  handleCheck = checkedKeys => {
    const checkedPaths = checkedKeys.map(key => key.split('/'));
    this.props.onSelect(checkedPaths);
  };

  handleLoadData = async treeNode => {
    const { treeData, treeDataByName } = await this.loadPath(
      treeNode.props.path,
      this.state
    );
    this.setState({ treeData, treeDataByName });
  };

  async loadPath(path, { treeData, treeDataByName }) {
    const { accountId } = this.props;
    const response = await rpcProxy.request(
      'getStorageChildren',
      accountId,
      path
    );
    const subtreeData = mapStorageChildren(response);
    const [rootName, ...parentsPath] = path;
    let subtreeItem = treeDataByName[rootName];
    for (const pathPart of parentsPath) {
      subtreeItem = subtreeItem.childrenByName[pathPart];
    }
    subtreeItem.children = subtreeData;
    subtreeItem.childrenByName = keyBy(subtreeData, 'name');
    return { treeData, treeDataByName };
  }

  async loadRoot() {
    const { accountId, selectedPaths } = this.props;
    this.setState({ isInitialLoading: true });
    const data = await rpcProxy.request('getStorageChildren', accountId, []);
    let treeData = mapStorageChildren(data);
    let treeDataByName = keyBy(treeData, 'name');

    const pathsToPreload = [];
    for (const path of selectedPaths) {
      if (path.length > 1) {
        /* eslint-disable no-plusplus */
        for (let index = 1, length = path.length; index <= length; index++) {
          pathsToPreload.push(path.slice(0, index));
        }
      }
    }

    for (const path of uniqWith(pathsToPreload, isEqual)) {
      // eslint-disable-next-line no-await-in-loop
      const response = await this.loadPath(path, { treeData, treeDataByName });
      treeData = response.treeData;
      treeDataByName = response.treeDataByName;
    }

    this.setState({
      isInitialLoading: false,
      treeData,
      treeDataByName,
    });
  }

  render() {
    const loop = (data, parentPath) =>
      data.map(item => {
        const currentPath = [...parentPath, item.name];
        const currentKey = currentPath.join('/');
        if (item.children) {
          return (
            <TreeNode key={currentKey} path={currentPath} title={item.name}>
              {loop(item.children, currentPath)}
            </TreeNode>
          );
        }
        return (
          <TreeNode key={currentKey} path={currentPath} title={item.name} />
        );
      });

    const { defaultExpandedPaths, selectedPaths } = this.props;
    const { isInitialLoading, treeData } = this.state;

    // showing loading indicator if loading initial tree from storage
    if (isInitialLoading) {
      return (
        <CircularProgress
          color={SECONDARY_COLOR}
          style={STYLES.loading}
          size={0.5}
        />
      );
    }

    // showing text if tree is empty -> so that user does not get confused with empty tree
    if (!isInitialLoading && treeData.length === 0) {
      return <p style={{ marginLeft: 23 }}>The storage is empty.</p>;
    }

    const checkedKeys = selectedPaths.map(path => path.join('/'));
    const defaultExpandedKeys = defaultExpandedPaths.map(path =>
      path.join('/')
    );
    const treeNodes = loop(treeData, []);

    return (
      <Tree
        checkable
        checkedKeys={checkedKeys}
        defaultExpandedKeys={defaultExpandedKeys}
        loadData={this.handleLoadData}
        onCheck={this.handleCheck}
      >
        {treeNodes}
      </Tree>
    );
  }
}

function mapStorageChildren(data) {
  return orderBy(data, 'name').map((item, index) => {
    return {
      hasChildren: item.has_children !== false,
      key: index,
      name: item.name,
    };
  });
}
