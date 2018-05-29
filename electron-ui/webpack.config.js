'use strict';

const path = require('path');

const webpack = require('webpack');

const config = {
  context: path.join(__dirname, 'renderer'),
  target: 'electron-renderer',
  entry: './main',
  module: {
    rules: [
      {
        test: /\.jsx?$/,
        exclude: /node_modules/,
        loader: 'babel-loader',
        options: {
          plugins: [
            'transform-async-to-generator',
            'transform-class-properties',
            'transform-object-rest-spread',
            [
              'transform-runtime',
              {
                helpers: true,
                polyfill: false,
                regenerator: true,
              },
            ],
          ],
          presets: ['react', 'es2015'],
        },
      },
      {
        test: /\.less$/,
        use: ['style-loader', 'css-loader', 'less-loader'],
      },
      {
        test: /\.css$/,
        use: ['style-loader', 'css-loader'],
      },
    ],
  },
  output: {
    path: path.join(__dirname, 'renderer-build'),
    filename: 'bundle.js',
  },
  plugins: [
    new webpack.DefinePlugin({
      'process.env': {
        NODE_ENV: JSON.stringify(process.env.NODE_ENV || 'development'),
      },
    }),
  ],
};

module.exports = config;
