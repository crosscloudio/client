import getMuiTheme from 'material-ui/lib/styles/getMuiTheme';
import merge from 'lodash/merge';

import { PRIMARY_COLOR, SECONDARY_COLOR } from './constants';

const baseTheme = getMuiTheme();

export default merge(baseTheme, {
  appBar: {
    color: PRIMARY_COLOR,
    height: 32,
  },
  textField: {
    focusColor: SECONDARY_COLOR,
  },
});
