# Third-party data

The TextFixer code is distributed under the MIT license (see `LICENSE`). **T9 dictionaries** (`<lang>.pkl.gz`
in GitHub Releases) are derived data from open sources; each dictionary is distributed
under the license terms of its sources:

* **Hunspell dictionaries** — the list of correct word forms (the T9 dictionary stores only their hashes
  and frequent words). The license is in the table below (for LibreOffice, in the dictionary folder's README).
* **Leipzig Corpora Collection** — frequencies of words and word pairs/triples. The downloadable corpora
  are distributed under the CC BY license ([terms](https://wortschatz.uni-leipzig.de/en/usage)).
  D. Goldhahn, T. Eckart, U. Quasthoff: *Building Large Monolingual Dictionaries at the Leipzig
  Corpora Collection: From 100 to 200 Languages.* LREC 2012.
* **wordfreq** (R. Speer) — word frequencies, data under CC BY-SA 4.0
  ([github.com/rspeer/wordfreq](https://github.com/rspeer/wordfreq)); used for the languages
  it supports.
* **Inter font** (language selection window) — SIL Open Font License 1.1, `textfixer/ui/fonts/LICENSE-Inter.txt`.

| Code | Language | Hunspell | Dictionary license | Leipzig corpus | Corpus license |
|---|---|---|---|---|---|
| ru | Русский | [wooorm/dictionaries (ru)](https://github.com/wooorm/dictionaries/tree/main/dictionaries/ru) | BSD-3-Clause | [rus_news_2024_1M](https://wortschatz.uni-leipzig.de/en/download) | CC BY 4.0 |
| en | English | [wooorm/dictionaries (en)](https://github.com/wooorm/dictionaries/tree/main/dictionaries/en) | (MIT AND BSD) | [eng_web_2014_1M](https://wortschatz.uni-leipzig.de/en/download) | CC BY 4.0 |
| uk | Українська | [wooorm/dictionaries (uk)](https://github.com/wooorm/dictionaries/tree/main/dictionaries/uk) | GPL-3.0 | [ukr_web_2012_1M](https://wortschatz.uni-leipzig.de/en/download) | CC BY 4.0 |
| de | Deutsch | [wooorm/dictionaries (de)](https://github.com/wooorm/dictionaries/tree/main/dictionaries/de) | (GPL-2.0 OR GPL-3.0) | [deu_web_2011_1M](https://wortschatz.uni-leipzig.de/en/download) | CC BY 4.0 |
| fr | Français | [wooorm/dictionaries (fr)](https://github.com/wooorm/dictionaries/tree/main/dictionaries/fr) | MPL-2.0 | [fra_news_2024_1M](https://wortschatz.uni-leipzig.de/en/download) | CC BY 4.0 |
| es | Español | [wooorm/dictionaries (es)](https://github.com/wooorm/dictionaries/tree/main/dictionaries/es) | (GPL-3.0 OR LGPL-3.0 OR MPL-1.1) | [spa_web_2016_1M](https://wortschatz.uni-leipzig.de/en/download) | CC BY 4.0 |
| it | Italiano | [wooorm/dictionaries (it)](https://github.com/wooorm/dictionaries/tree/main/dictionaries/it) | GPL-3.0 | [ita_web_2011_1M](https://wortschatz.uni-leipzig.de/en/download) | CC BY 4.0 |
| pt | Português | [wooorm/dictionaries (pt-PT)](https://github.com/wooorm/dictionaries/tree/main/dictionaries/pt-PT) | (GPL-2.0 OR LGPL-2.1 OR MPL-1.1) | [por_news_2024_1M](https://wortschatz.uni-leipzig.de/en/download) | CC BY 4.0 |
| pl | Polski | [wooorm/dictionaries (pl)](https://github.com/wooorm/dictionaries/tree/main/dictionaries/pl) | (GPL-3.0 OR LGPL-3.0 OR MPL-2.0) | [pol_news_2024_1M](https://wortschatz.uni-leipzig.de/en/download) | CC BY 4.0 |
| tr | Türkçe | [wooorm/dictionaries (tr)](https://github.com/wooorm/dictionaries/tree/main/dictionaries/tr) | MIT | [tur_news_2024_1M](https://wortschatz.uni-leipzig.de/en/download) | CC BY 4.0 |
| nl | Nederlands | [wooorm/dictionaries (nl)](https://github.com/wooorm/dictionaries/tree/main/dictionaries/nl) | (BSD-3-Clause OR CC-BY-3.0) | [nld_news_2024_1M](https://wortschatz.uni-leipzig.de/en/download) | CC BY 4.0 |
| cs | Čeština | [wooorm/dictionaries (cs)](https://github.com/wooorm/dictionaries/tree/main/dictionaries/cs) | GPL-2.0 | [ces_web_2012_1M](https://wortschatz.uni-leipzig.de/en/download) | CC BY 4.0 |
| sk | Slovenčina | [wooorm/dictionaries (sk)](https://github.com/wooorm/dictionaries/tree/main/dictionaries/sk) | (GPL-2.0 OR LGPL-2.1 OR MPL-1.1) | [slk_newscrawl_2016_1M](https://wortschatz.uni-leipzig.de/en/download) | CC BY 4.0 |
| hu | Magyar | [wooorm/dictionaries (hu)](https://github.com/wooorm/dictionaries/tree/main/dictionaries/hu) | (GPL-2.0 OR LGPL-2.1 OR MPL-1.1) | [hun_news_2024_1M](https://wortschatz.uni-leipzig.de/en/download) | CC BY 4.0 |
| ro | Română | [wooorm/dictionaries (ro)](https://github.com/wooorm/dictionaries/tree/main/dictionaries/ro) | (GPL-2.0 OR LGPL-2.1 OR MPL-1.1) | [ron_web_2011_1M](https://wortschatz.uni-leipzig.de/en/download) | CC BY 4.0 |
| bg | Български | [wooorm/dictionaries (bg)](https://github.com/wooorm/dictionaries/tree/main/dictionaries/bg) | (GPL-2.0 OR LGPL-2.1 OR MPL-1.1) | [bul_news_2022_1M](https://wortschatz.uni-leipzig.de/en/download) | CC BY 4.0 |
| el | Ελληνικά | [wooorm/dictionaries (el)](https://github.com/wooorm/dictionaries/tree/main/dictionaries/el) | (GPL-2.0 OR LGPL-2.1 OR MPL-1.1) | [ell_web_2011_1M](https://wortschatz.uni-leipzig.de/en/download) | CC BY 4.0 |
| sv | Svenska | [wooorm/dictionaries (sv)](https://github.com/wooorm/dictionaries/tree/main/dictionaries/sv) | LGPL-3.0 | [swe_news_2023_1M](https://wortschatz.uni-leipzig.de/en/download) | CC BY 4.0 |
| da | Dansk | [wooorm/dictionaries (da)](https://github.com/wooorm/dictionaries/tree/main/dictionaries/da) | (GPL-2.0 OR LGPL-2.1 OR MPL-1.1) | [dan_newscrawl_2023_1M](https://wortschatz.uni-leipzig.de/en/download) | CC BY 4.0 |
| nb | Norsk | [wooorm/dictionaries (nb)](https://github.com/wooorm/dictionaries/tree/main/dictionaries/nb) | GPL-2.0 | [nob_newscrawl_2019_1M](https://wortschatz.uni-leipzig.de/en/download) | CC BY 4.0 |
| fi | Suomi | — | — | [fin_news_2022_1M](https://wortschatz.uni-leipzig.de/en/download) | CC BY 4.0 |
| et | Eesti | [wooorm/dictionaries (et)](https://github.com/wooorm/dictionaries/tree/main/dictionaries/et) | LGPL-2.1 | [est_newscrawl_2017_1M](https://wortschatz.uni-leipzig.de/en/download) | CC BY 4.0 |
| lv | Latviešu | [wooorm/dictionaries (lv)](https://github.com/wooorm/dictionaries/tree/main/dictionaries/lv) | LGPL-2.1 | [lav_newscrawl_2016_1M](https://wortschatz.uni-leipzig.de/en/download) | CC BY 4.0 |
| lt | Lietuvių | [wooorm/dictionaries (lt)](https://github.com/wooorm/dictionaries/tree/main/dictionaries/lt) | BSD-3-Clause | [lit_news_2020_1M](https://wortschatz.uni-leipzig.de/en/download) | CC BY 4.0 |
| sl | Slovenščina | [wooorm/dictionaries (sl)](https://github.com/wooorm/dictionaries/tree/main/dictionaries/sl) | (GPL-3.0 OR LGPL-2.1) | [slv_news_2020_1M](https://wortschatz.uni-leipzig.de/en/download) | CC BY 4.0 |
| hr | Hrvatski | [wooorm/dictionaries (hr)](https://github.com/wooorm/dictionaries/tree/main/dictionaries/hr) | (LGPL-2.1 OR SISSL) | [hrv_news_2020_1M](https://wortschatz.uni-leipzig.de/en/download) | CC BY 4.0 |
| sr | Српски | [wooorm/dictionaries (sr)](https://github.com/wooorm/dictionaries/tree/main/dictionaries/sr) | (GPL-2.0 OR LGPL-2.1 OR MPL-1.1 OR CC-BY-SA-3.0) | [srp_wikipedia_2021_1M](https://wortschatz.uni-leipzig.de/en/download) | CC BY 4.0 |
| bs | Bosanski | [LibreOffice/dictionaries (bs_BA/bs_BA)](https://github.com/LibreOffice/dictionaries/tree/master/bs_BA) | see the folder's README | [bos_news_2020_300K](https://wortschatz.uni-leipzig.de/en/download) | CC BY 4.0 |
| mk | Македонски | [wooorm/dictionaries (mk)](https://github.com/wooorm/dictionaries/tree/main/dictionaries/mk) | GPL-3.0 | [mkd_newscrawl_2011_300K](https://wortschatz.uni-leipzig.de/en/download) | CC BY 4.0 |
| sq | Shqip | [LibreOffice/dictionaries (sq_AL/sq_AL)](https://github.com/LibreOffice/dictionaries/tree/master/sq_AL) | see the folder's README | [sqi_news_2020_1M](https://wortschatz.uni-leipzig.de/en/download) | CC BY 4.0 |
| be | Беларуская | — | — | [bel_newscrawl_2015_1M](https://wortschatz.uni-leipzig.de/en/download) | CC BY 4.0 |
| ga | Gaeilge | [wooorm/dictionaries (ga)](https://github.com/wooorm/dictionaries/tree/main/dictionaries/ga) | GPL-2.0 | [gle_newscrawl_2014_300K](https://wortschatz.uni-leipzig.de/en/download) | CC BY 4.0 |
| cy | Cymraeg | [wooorm/dictionaries (cy)](https://github.com/wooorm/dictionaries/tree/main/dictionaries/cy) | LGPL-3.0 | [cym_wikipedia_2021_100K](https://wortschatz.uni-leipzig.de/en/download) | CC BY 4.0 |
| is | Íslenska | [wooorm/dictionaries (is)](https://github.com/wooorm/dictionaries/tree/main/dictionaries/is) | CC-BY-SA-3.0 | [isl_newscrawl_2011_1M](https://wortschatz.uni-leipzig.de/en/download) | CC BY 4.0 |
| mt | Malti | — | — | [mlt_web_2012_300K](https://wortschatz.uni-leipzig.de/en/download) | CC BY 4.0 |
| ca | Català | [wooorm/dictionaries (ca)](https://github.com/wooorm/dictionaries/tree/main/dictionaries/ca) | (GPL-2.0 OR LGPL-2.1) | [cat_newscrawl_2016_1M](https://wortschatz.uni-leipzig.de/en/download) | CC BY 4.0 |
| eu | Euskara | [wooorm/dictionaries (eu)](https://github.com/wooorm/dictionaries/tree/main/dictionaries/eu) | GPL-2.0 | [eus_newscrawl_2012_300K](https://wortschatz.uni-leipzig.de/en/download) | CC BY 4.0 |
| gl | Galego | [wooorm/dictionaries (gl)](https://github.com/wooorm/dictionaries/tree/main/dictionaries/gl) | GPL-3.0 | [glg_wikipedia_2021_300K](https://wortschatz.uni-leipzig.de/en/download) | CC BY 4.0 |
| lb | Lëtzebuergesch | [wooorm/dictionaries (lb)](https://github.com/wooorm/dictionaries/tree/main/dictionaries/lb) | EUPL-1.1 | [ltz_newscrawl_2016_300K](https://wortschatz.uni-leipzig.de/en/download) | CC BY 4.0 |
| id | Bahasa Indonesia | [LibreOffice/dictionaries (id/id_ID)](https://github.com/LibreOffice/dictionaries/tree/master/id) | see the folder's README | [ind_web_2012_1M](https://wortschatz.uni-leipzig.de/en/download) | CC BY 4.0 |
| ms | Bahasa Melayu | — | — | [msa_newscrawl_2016_300K](https://wortschatz.uni-leipzig.de/en/download) | CC BY 4.0 |
| vi | Tiếng Việt | [wooorm/dictionaries (vi)](https://github.com/wooorm/dictionaries/tree/main/dictionaries/vi) | GPL-2.0 | [vie_news_2022_1M](https://wortschatz.uni-leipzig.de/en/download) | CC BY 4.0 |
| tl | Filipino | — | — | [tgl_wikipedia_2021_100K](https://wortschatz.uni-leipzig.de/en/download) | CC BY 4.0 |
| sw | Kiswahili | [LibreOffice/dictionaries (sw_TZ/sw_TZ)](https://github.com/LibreOffice/dictionaries/tree/master/sw_TZ) | see the folder's README | [swa_wikipedia_2021_100K](https://wortschatz.uni-leipzig.de/en/download) | CC BY 4.0 |
| az | Azərbaycanca | — | — | [aze_newscrawl_2013_1M](https://wortschatz.uni-leipzig.de/en/download) | CC BY 4.0 |
| uz | Oʻzbekcha | — | — | [uzb_newscrawl_2011_100K](https://wortschatz.uni-leipzig.de/en/download) | CC BY 4.0 |
| af | Afrikaans | [LibreOffice/dictionaries (af_ZA/af_ZA)](https://github.com/LibreOffice/dictionaries/tree/master/af_ZA) | see the folder's README | [afr_mixed_2019_1M](https://wortschatz.uni-leipzig.de/en/download) | CC BY 4.0 |
| eo | Esperanto | [wooorm/dictionaries (eo)](https://github.com/wooorm/dictionaries/tree/main/dictionaries/eo) | GPL-2.0 | [epo_web_2012_1M](https://wortschatz.uni-leipzig.de/en/download) | CC BY 4.0 |
| la | Latina | [wooorm/dictionaries (la)](https://github.com/wooorm/dictionaries/tree/main/dictionaries/la) | GPL-2.0 | [lat_wikipedia_2021_100K](https://wortschatz.uni-leipzig.de/en/download) | CC BY 4.0 |
