module.exports = {
  extends: ['eslint-config-airbnb', 'prettier', 'prettier/react'],
  parser: 'babel-eslint',
  env: {
    browser: true,
    es6: true,
    jest: true,
    mocha: true,
    node: true,
  },
  globals: {
    expect: true,
    jest: true,
  },
  plugins: ['babel', 'prettier'],
  rules: {
    'arrow-body-style': 0,
    'class-methods-use-this': 0,
    // like in eslint-config-airbnb-base, but not for functions
    // to allow run non-transpiled on node 6
    'comma-dangle': ['error', {
      arrays: 'always-multiline',
      objects: 'always-multiline',
      imports: 'always-multiline',
      exports: 'always-multiline',
      functions: 'never',
    }],
    'func-names': 0,
    'linebreak-style': 0,
    'new-cap': 0,
    'newline-per-chained-call': 0,
    'no-param-reassign': [2, { props: false }],
    // copied from eslint-config-airbnb-base, but allow iterators/generators
    'no-restricted-syntax': [
      'error',
      {
        selector: 'ForInStatement',
        message:
          'for..in loops iterate over the entire prototype chain, which is virtually never what you want. Use Object.{keys,values,entries}, and iterate over the resulting array.',
      },
      {
        selector: 'LabeledStatement',
        message:
          'Labels are a form of GOTO; using them makes code confusing and hard to maintain and understand.',
      },
      {
        selector: 'WithStatement',
        message:
          '`with` is disallowed in strict mode because it makes code impossible to predict and optimize.',
      },
    ],
    'no-unused-expressions': [
      2,
      { allowShortCircuit: true, allowTernary: true },
    ],
    'no-use-before-define': [2, 'nofunc'],
    'no-useless-return': 0,
    'padded-blocks': 0,
    quotes: ['error', 'single', { avoidEscape: true }],
    strict: 0,
    'import/extensions': 0,
    // not used, because of mappings in webpack (it is allowed to import some
    // local modules without './' or '../')
    'import/first': 0,
    'import/no-extraneous-dependencies': 0,
    'import/no-unresolved': 0,
    'import/prefer-default-export': 0,
    'jsx-a11y/label-has-for': 0,
    'jsx-a11y/no-noninteractive-element-interactions': 0,
    'jsx-a11y/no-static-element-interactions': 0,
    'react/jsx-filename-extension': 0,
    'react/jsx-no-target-blank': 0,
    'react/forbid-prop-types': 0,
    'react/prefer-stateless-function': 0,
    'react/prop-types': 0,
    'react/require-default-props': 0,
  },
};
