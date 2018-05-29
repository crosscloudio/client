const childProcess = require('child_process');
const fs = require('fs');
const path = require('path');

const gulp = require('gulp');
const gutil = require('gulp-util');
const rimraf = require('rimraf');
const runSequence = require('run-sequence');
const webpack = require('webpack');

const baseWebpackConfig = require('./webpack.config');

const nodeDotBinPath = path.join(__dirname, 'node_modules', '.bin');

const productionEnv = Object.assign({}, process.env, {
  NODE_ENV: 'production',
  PATH: `${nodeDotBinPath}${path.delimiter}${process.env.PATH}`,
});

gulp.task('clean', callback => {
  rimraf('./build', callback);
});

gulp.task('webpack', callback => {
  const webpackConfig = Object.assign({}, baseWebpackConfig, {
    output: Object.assign({}, baseWebpackConfig.output, {
      path: path.join(__dirname, 'build/renderer-build'),
    }),
    plugins: baseWebpackConfig.plugins.concat([
      new webpack.optimize.UglifyJsPlugin({
        sourceMap: false,
        compress: { warnings: false },
      }),
    ]),
  });

  webpack(webpackConfig, (error, stats) => {
    if (error) {
      throw new gutil.PluginError('webpack', error);
    }

    gutil.log('[webpack]', stats.toString({ chunks: false }));
    callback();
  });
});

gulp.task('baseFiles', () => {
  return gulp
    .src(['package.json', 'index.{html,js}', 'yarn.lock'])
    .pipe(gulp.dest('build'));
});

gulp.task('release-json', callback => {
  const gitRevision = childProcess
    .execSync('git rev-parse HEAD', {
      encoding: 'utf8',
    })
    .trim();
  fs.writeFile(
    path.join(__dirname, 'build', 'release.json'),
    JSON.stringify({
      git_rev: gitRevision,
    }),
    callback
  );
});

gulp.task('assets', () => {
  return gulp.src('assets/**/*.{png,svg,ico}').pipe(gulp.dest('build/assets'));
});

gulp.task('platform-icon', () => {
  const iconExtension = process.platform === 'darwin' ? 'icns' : 'ico';
  return gulp
    .src(`assets/icon.${iconExtension}`)
    .pipe(gulp.dest('build/build'));
});

gulp.task('shellCode', () => {
  return gulp.src('shell/**/*.js').pipe(gulp.dest('build/shell'));
});

gulp.task('yarn', () => {
  childProcess.execSync('yarn install', {
    cwd: path.join(__dirname, 'build'),
    env: productionEnv,
    stdio: 'inherit',
  });
});

gulp.task('electron', () => {
  const commandPath = path.join(
    __dirname,
    'node_modules',
    '.bin',
    'electron-builder'
  );
  const command = `${commandPath}`;

  childProcess.execSync(command, {
    cwd: path.join(__dirname, 'build'),
    env: productionEnv,
    stdio: 'inherit',
  });
});

gulp.task('build', callback => {
  runSequence(
    'clean',
    ['webpack', 'baseFiles', 'assets', 'shellCode', 'platform-icon'],
    // run after tasks above because requires `build` dir
    'release-json',
    'yarn',
    'electron',
    callback
  );
});
