HanaMinA/B/C-subset.woff2 是「花园明朝」(Hanazono Mincho) 的子集，只含本站正文用到的扩展区汉字，
用作 assets/css/extended/custom.css 中的生僻字兜底字体。

来源：https://github.com/cjkvi/HanaMinAFDKO （版本 8.030）
版权：2007-2018 GlyphWiki. All Rights Reserved.
许可：按 GlyphWiki 许可（http://glyphwiki.org/license.html，见该项目 README 的 Licence 一节）。

重新生成（正文新增生僻字后）：
  pip install fonttools brotli
  python3 scripts/build_rare_font.py <存放 HanaMinA/B/C.otf 的目录>
