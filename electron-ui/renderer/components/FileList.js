import CheckCircleIcon from 'material-ui/lib/svg-icons/action/check-circle';
import { green400 } from 'material-ui/lib/styles/colors';
import List from 'material-ui/lib/lists/list';
import ListItem from 'material-ui/lib/lists/list-item';
import React, { PropTypes } from 'react';

const STYLES = {
  list: {
    width: '100%',
    paddingTop: 0,
    paddingBottom: 0,
  },
  item: {
    width: '100%',
    fontSize: 14,
    cursor: 'default',
  },
  notFirstItem: {
    borderTop: '1px solid rgba(158, 158, 158, 0.25)',
  },
  itemInnerDiv: {
    paddingTop: 10,
    paddingBottom: 10,
    paddingLeft: 60,
  },
  itemText: {
    display: 'block',
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    whiteSpace: 'nowrap',
  },
  itemTextExtra: {
    marginTop: 4,
    fontSize: 12,
    color: 'rgba(0, 0, 0, 0.298039)',
  },
  image: {
    width: 27,
    height: 27,
    marginTop: 7,
  },
  doneIcon: {
    top: 0,
    width: 16,
    height: 16,
    margin: 10,
    marginTop: 20,
  },
};

export default class FileList extends React.Component {
  static propTypes = {
    files: PropTypes.array.isRequired,
    onItemClick: PropTypes.func.isRequired,
  };

  handleItemClick(path) {
    this.props.onItemClick(path);
  }

  renderFile = (file, index) => {
    const fileName = file.path[file.path.length - 1];
    return (
      <ListItem
        innerDivStyle={STYLES.itemInnerDiv}
        key={index}
        leftAvatar={
          <img
            alt=""
            src={`assets/file_icons/${file.iconName}`}
            style={STYLES.image}
          />
        }
        onClick={// eslint-disable-line react/jsx-no-bind
        this.handleItemClick.bind(this, file.path)}
        primaryText={
          <div>
            <div style={STYLES.itemText}>
              {fileName}
            </div>
            <div
              style={{
                ...STYLES.itemText,
                ...STYLES.itemTextExtra,
              }}
            >
              {file.operationType} {file.time}
            </div>
          </div>
        }
        rightIcon={<CheckCircleIcon style={STYLES.doneIcon} color={green400} />}
        style={{
          ...STYLES.item,
          ...(index === 0 ? {} : STYLES.notFirstItem),
        }}
      />
    );
  };

  render() {
    const { files } = this.props;
    return (
      <List style={STYLES.list}>
        {files.map(this.renderFile)}
      </List>
    );
  }
}
