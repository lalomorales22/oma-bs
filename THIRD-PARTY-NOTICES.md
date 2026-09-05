# Attribution and dependencies

OMA-BS and its browser studio are maintained by Lalo Morales. The browser studio
is adapted from his [Chroma Canvas](https://github.com/lalomorales22/Chroma-Canvas).
The original repository had no license file when this fork was prepared; the
included MIT license is for this owner-maintained OMA-BS distribution. Historical
Chroma Canvas storage names remain for compatibility with saved browser projects.

Capture integration follows and adapts the
[Omarchy helpers](https://github.com/basecamp/omarchy/tree/quattro/bin).
Their MIT notice is reproduced below. Omarchy and platform names identify
compatibility; this project does not claim endorsement by those projects.

## Omarchy notice

Copyright (c) David Heinemeier Hansson

Permission is hereby granted, free of charge, to any person obtaining
a copy of this software and associated documentation files (the
"Software"), to deal in the Software without restriction, including
without limitation the rights to use, copy, modify, merge, publish,
distribute, sublicense, and/or sell copies of the Software, and to
permit persons to whom the Software is furnished to do so, subject to
the following conditions:

The above copyright notice and this permission notice shall be
included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE
LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION
WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

## Separately installed software

GPU Screen Recorder, FFmpeg/ffprobe, mpv, Qt, Quickshell, Python, Node.js, and
Omarchy are external dependencies, not binaries bundled in this archive. Their
licenses remain their own; distribution packages provide applicable notices.

The browser's direct and transitive dependencies are recorded in
`studio/package.json` and `studio/package-lock.json`. React, Lucide, Three.js,
mp4-muxer, ws, QRCode, Google GenAI, Vite, TypeScript, Tailwind, and other npm
packages retain their package licenses. Inter is installed through
`@fontsource-variable/inter` with its SIL Open Font License. Dependency license
files stay in the separate npm runtime. Do not remove their notices when
redistributing a compiled browser bundle. This source archive contains neither
node_modules nor a prebuilt browser bundle.
