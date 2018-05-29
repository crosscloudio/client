import React from 'react';
import { ipcRenderer } from 'electron';
import { isEqual, uniqWith } from 'lodash';

import BaseDialog from './BaseDialog';
import Button from '../common/Button';
import SelectiveSyncTree from './selectiveSync/SelectiveSyncTree';
import './SelectiveSyncDialog.css';
import appEventBus from '../../utils/appEventBus';
import redirectedRpc from '../../utils/redirectedRpc';
import rpcProxy from '../../utils/rpcProxy';

const STYLES = {
  header: {
    marginBottom: 8,
    fontSize: '1.2em',
    fontWeight: 'bold',
  },
  inner: {
    padding: 15,
  },
  inputInfo: {
    display: 'block',
    marginLeft: 20,
    marginBottom: 8,
  },
  okButton: {
    marginLeft: 8,
  },
  radio: {
    marginRight: 8,
  },
  subheader: {
    marginBottom: 8,
  },
  tree: {
    maxHeight: 150,
    overflowY: 'auto',
  },
};

const initalState = {
  accountId: null,
  defaultExpandedPaths: [],
  resolver: null,
  selectedPaths: [],
  syncAll: true,
};

export default class SelectiveSyncDialog extends React.Component {
  constructor(props, context) {
    super(props, context);
    this.state = { ...initalState };
  }

  componentDidMount() {
    redirectedRpc.on('selectSyncPaths', this.handleSelectSyncPathsRequested);
    appEventBus.on(
      'selectSyncPaths',
      this.handleSelectSyncPathsFromMenuRequested
    );
  }

  componentWillUnmount() {
    redirectedRpc.removeListener(
      'selectSyncPaths',
      this.handleSelectSyncPathsRequested
    );
    appEventBus.removeListener(
      'selectSyncPaths',
      this.handleSelectSyncPathsFromMenuRequested
    );
  }

  handleHide = () => {
    this.toggleMenubarExpanded(false);
  };

  handleOkClick = () => {
    const { accountId, resolver, selectedPaths, syncAll } = this.state;
    const paths = syncAll ? [[]] : selectedPaths;
    const result = mapPaths(paths);
    if (resolver) {
      // was invoked by the core
      resolver.respondWith(result);
    } else {
      // was invoked by the user action in menu
      rpcProxy.request('setSelectedSyncPaths', accountId, result);
    }
    this.dialog.hide();
  };

  handleCancel = () => {
    const { resolver } = this.state;
    if (resolver) {
      // We only handle the case where the backend caused the dialog to show, not the user

      // This resolves to "sync all"
      const result = mapPaths([[]]);
      resolver.respondWith(result);
    }
    this.dialog.hide();
  };

  handleSelectSyncPathsFromMenuRequested = async ({ accountId }) => {
    const paths = await rpcProxy.request('getSelectedSyncPaths', accountId);
    const defaultExpandedPaths = [];
    const selectedPathArrays = paths.map(item => item.path);
    const selectedPathsStringified = selectedPathArrays.reduce(
      (result, path) => {
        if (path.length > 0) {
          result[path.join('/')] = true;
        }
        return result;
      },
      Object.create(null)
    );
    selectedPathArrays.forEach(path => {
      if (path.length > 1) {
        /* eslint-disable no-plusplus */
        for (
          let index = 1, length = path.length;
          index <= length - 1;
          index++
        ) {
          const partialPath = path.slice(0, index);
          const stringifiedPartialPath = partialPath.join('/');
          if (stringifiedPartialPath) {
            selectedPathsStringified[stringifiedPartialPath] = false;
            defaultExpandedPaths.push(partialPath);
          }
        }
      }
    });
    const selectedPaths = Object.keys(selectedPathsStringified)
      .filter(stringifiedPath => selectedPathsStringified[stringifiedPath])
      .map(stringifiedPath => {
        if (stringifiedPath) {
          return stringifiedPath.split('/');
        }
        return [];
      });
    const syncAll = isEqual(selectedPathArrays, [[]]);
    this.setState({
      ...initalState,
      accountId,
      defaultExpandedPaths,
      selectedPaths,
      syncAll,
    });

    // expanding menubar if not all is selected
    if (!this.state.syncAll) {
      this.toggleMenubarExpanded(true);
    }

    this.show();
  };

  handleSelectSyncPathsRequested = (resolver, { accountId }) => {
    this.setState({
      ...initalState,
      accountId,
      resolver,
    });
    this.show();
  };

  handleSyncAllChange = event => {
    const syncAll = event.target.value === '1';
    const newState = { syncAll };
    if (syncAll) {
      newState.selectedPaths = [];
      this.toggleMenubarExpanded(false);
    } else {
      this.toggleMenubarExpanded(true);
    }
    this.setState(newState);
  };

  handleTreeSelect = selectedPaths => {
    this.setState({ selectedPaths });
  };

  toggleMenubarExpanded(expand) {
    ipcRenderer.send('toggleMenubarExpanded', { expand });
  }

  show = () => {
    this.dialog.show();
  };

  render() {
    const {
      accountId,
      defaultExpandedPaths,
      selectedPaths,
      syncAll,
    } = this.state;

    const okAction = (
      <Button label="Ok" onClick={this.handleOkClick} style={STYLES.okButton} />
    );

    return (
      <BaseDialog
        actions={[okAction]}
        autoDetectWindowHeight
        onCancel={this.handleCancel}
        onHide={this.handleHide}
        ref={dialog => {
          this.dialog = dialog;
        }}
        repositionOnUpdate={false}
        style={{ top: 32 }}
        title=""
        titleStyle={{ display: 'none' }}
      >
        <div className="SelectiveSyncDialog" style={STYLES.inner}>
          <p style={STYLES.header}>Selective Sync</p>
          <p style={STYLES.subheader}>
            You can either sync all data from the storage or choose specific
            folders to sync.
          </p>
          <form>
            <div>
              <p>
                <label>
                  <input
                    checked={syncAll}
                    name="syncAll"
                    onChange={this.handleSyncAllChange}
                    style={STYLES.radio}
                    type="radio"
                    value="1"
                  />
                  <b>Sync all data from this storage</b>
                </label>
              </p>
            </div>
            <div>
              <p>
                <label>
                  <input
                    checked={!syncAll}
                    name="syncAll"
                    onChange={this.handleSyncAllChange}
                    style={STYLES.radio}
                    type="radio"
                    value="0"
                  />
                  <b>Choose folders to sync</b>
                </label>
              </p>
            </div>
          </form>
          {syncAll
            ? null
            : <div style={STYLES.tree}>
                <SelectiveSyncTree
                  accountId={accountId}
                  defaultExpandedPaths={defaultExpandedPaths}
                  onSelect={this.handleTreeSelect}
                  selectedPaths={selectedPaths}
                />
              </div>}
        </div>
      </BaseDialog>
    );
  }
}

function mapPaths(paths) {
  const allPaths = [];
  for (const path of paths) {
    if (path.length > 0) {
      /* eslint-disable no-plusplus */
      for (let index = 1, length = path.length; index <= length; index++) {
        allPaths.push(path.slice(0, index));
      }
    }
  }
  if (paths.length > 0) {
    allPaths.push([]);
  }
  const uniquePaths = uniqWith(allPaths, isEqual);
  return uniquePaths.map(path => ({ path, children: true }));
}
