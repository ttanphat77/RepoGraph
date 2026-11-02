# Độ phủ doc, số lượng commit và issue của các repo SWE-bench

Cập nhật ngày 26/10/2026. File này tổng hợp các phép đo ngày 23 đến 26/10/2026 trên 47 repo của SWE-bench: 35 repo phần train và 12 repo tập test (cũng là 12 repo của Lite và Verified). Số liệu sinh từ các file kết quả trong `D:\tmp\rgcov` bằng script, không chép tay.

Bảng độ phủ được lập để đo độ phủ doc ảnh hưởng thế nào tới hiệu quả truy hồi. Vì vậy repo có độ phủ thấp được giữ trong thực nghiệm. Phân tích nằm ở mục 10.2 của `pipeline_design.md` và mục 13.6 của `research_context.md` (quyết định 60, ngày 28/10/2026).

## 1. Cách đo

- **Snapshot.** Issue của mỗi repo được chia thành các cửa sổ 60 ngày trong cùng version, như cell `scale-data`. Snapshot là base commit sớm nhất của cửa sổ có nhiều issue nhất. Với phần train, issue lấy từ phần train; với 12 repo tập test, issue lấy từ tập test. Riêng Django và SymPy dùng snapshot của thực nghiệm (838e432e, 9bf73cc2).
- **Độ phủ doc.** Tỷ lệ hàm/lớp có ít nhất một cạnh `Documents`. Graph dựng bằng chính code của notebook (cell `9df72df0`, bỏ bước embedding), nên cạnh được tạo theo đúng cách nối của đề tài: vai trò RST (`:func:`, `:class:`, ...) và directive (`.. autoclass::`, `.. class::`, ...) trong thư mục doc ở gốc repo.
- **Commit.** Đếm từ lịch sử git tới snapshot. Nhánh chính là `git log --first-parent`, như nguồn HIST. Cửa sổ 5 năm trước snapshot là `HIST_YEARS` của đề tài.
- **Issue.** Đếm qua API tìm kiếm của GitHub, không dùng token: issue đã đóng và pull request đã merge, đều tạo trước ngày của snapshot. Django dùng Trac nên đếm từ dữ liệu Trac đã cào (ticket có resolution là fixed). Không đọc nội dung từng mục.
- **Thử crawl.** Commit: lấy diff và tính hàm/lớp bị sửa bằng đúng các hàm của `build_history` cho 5 commit mỗi repo, trên 3 repo. Issue: tải 1 trang (100 mục) danh sách issue đã đóng ở 3 repo, và 1 trang CSV của Trac.

## 2. Bảng tổng hợp

| Repo | Lite và Verified | Snapshot | Độ phủ doc | Commit nhánh chính trong 5 năm (có sửa `.py`) | Issue đã đóng trước snapshot | PR đã merge trước snapshot |
|---|---|---|---|---|---|---|
| pyca/cryptography |  | f12955cd (2017-06-07) | 37,6% | 2.360 (1.562) | 943 | 2.437 |
| pallets/flask | ✓ | 7ee9ceb7 (2023-03-11) | 24,0% | 576 (292) | 2.464 | 1.438 |
| django/django | ✓ | 838e432e (2019-01-19) | 17,7% | 9.456 (6.810) | 16.189 | - |
| pydata/xarray | ✓ | f52a95cb (2021-01-12) | 12,7% | 1.651 (1.217) | 2.223 | 1.964 |
| huggingface/transformers |  | 60fc0329 (2020-09-07) | 12,5% | 3.105 (2.041) | 4.235 | 2.117 |
| scikit-learn/scikit-learn | ✓ | 4223633b (2019-01-03) | 11,9% | 4.058 (2.926) | 5.439 | 4.316 |
| pandas-dev/pandas |  | ed116557 (2020-08-17) | 9,6% | 11.033 (9.075) | 17.999 | 12.473 |
| sympy/sympy | ✓ | 9bf73cc2 (2018-01-08) | 8,2% | 3.254 (2.915) | 5.792 | 4.316 |
| mwaskom/seaborn | ✓ | a1ede5eb (2022-08-07) | 6,4% | 458 (375) | 2.023 | 644 |
| astropy/astropy | ✓ | b185ca18 (2022-08-09) | 5,6% | 3.166 (2.339) | 4.478 | 6.921 |
| apache/airflow |  | 0620aaa0 (2020-10-10) | 5,5% | 7.214 (5.018) | 1.922 | 5.955 |
| Lightning-AI/lightning |  | 9e8716af (2020-06-08) | 5,2% | 1.598 (1.090) | 1.047 | 869 |
| wagtail/wagtail |  | 992d4c4e (2023-01-30) | 4,4% | 6.032 (3.040) | 3.763 | 2.980 |
| scipy/scipy |  | 8741fe19 (2014-07-31) | 4,3% | 2.598 (2.145) | 2.466 | 860 |
| psf/requests | ✓ | 9968a10f (2013-09-25) | 3,5% | 992 (691) | 853 | 532 |
| sphinx-doc/sphinx | ✓ | 07983a5a (2020-12-27) | 3,2% | 2.671 (1.874) | 4.678 | 2.992 |
| twisted/twisted |  | 9c1b10a1 (2022-09-22) | 3,1% | 675 (573) | 7.399 | 1.274 |
| pytest-dev/pytest | ✓ | d4dfe863 (2020-05-16) | 3,0% | 1.927 (1.178) | 3.691 | 2.767 |
| celery/celery |  | 66d2ea51 (2020-10-06) | 2,9% | 2.083 (1.329) | 3.993 | 1.339 |
| gitpython-developers/GitPython |  | 651a81de (2021-04-14) | 2,9% | 628 (434) | 743 | 324 |
| matplotlib/matplotlib | ✓ | f0f13394 (2023-06-28) | 2,8% | 6.675 (5.696) | 9.001 | 14.189 |
| ipython/ipython |  | 9be9a917 (2013-07-12) | 2,2% | 2.281 (1.799) | 1.864 | 1.315 |
| dagster-io/dagster |  | bd405854 (2023-05-22) | 2,1% | 13.989 (9.898) | 4.296 | 7.187 |
| google/jax |  | 64b1da9d (2020-03-05) | 2,0% | 1.759 (1.387) | 917 | 1.234 |
| numpy/numpy |  | 0934653e (2013-02-28) | 1,7% | 3.966 (2.597) | 2.364 | 318 |
| ray-project/ray |  | 5b330de1 (2020-05-18) | 1,5% | 4.402 (2.875) | 3.537 | 4.101 |
| googleapis/google-cloud-python |  | 935f1d7c (2018-09-17) | 1,0% | 2.999 (2.553) | 2.379 | 3.201 |
| Qiskit/qiskit |  | eddef45d (2019-04-27) | 0,3% | 1.120 (939) | 906 | 1.103 |
| pylint-dev/pylint | ✓ | 789a3818 (2022-03-30) | 0,2% | 3.102 (2.378) | 3.704 | 1.751 |
| ytdl-org/youtube-dl |  | af9e7250 (2022-01-31) | 0,04% | 4.265 (3.872) | 21.326 | 1.497 |
| apache/mxnet |  | 52793a15 (2015-11-18) | 0,0% | 532 (210) | 219 | 372 |
| conan-io/conan |  | 84d3c55c (2019-02-13) | 0,0% | 608 (545) | 2.675 | 1.595 |
| conda/conda |  | 58f340d4 (2017-11-27) | 0,0% | 3.454 (2.706) | 4.677 | 1.246 |
| DataDog/integrations-core |  | 09dae880 (2018-04-11) | 0,0% | 1.180 (670) | 121 | 1.107 |
| docker/compose |  | 4017ea99 (2016-01-05) | 0,0% | 1.012 (577) | 1.524 | 761 |
| explosion/spaCy |  | 03d58f9f (2019-01-30) | 0,0% | 3.138 (1.607) | 2.426 | 659 |
| jupyterlab/jupyterlab |  | d02fcfda (2020-07-26) | 0,0% | 3.852 (617) | 3.828 | 3.476 |
| kubeflow/pipelines |  | 0cd052b3 (2019-05-08) | 0,0% | 661 (273) | 473 | 703 |
| mesonbuild/meson |  | cd6d5a64 (2016-10-08) | 0,0% | 2.006 (1.810) | 439 | 340 |
| open-mmlab/mmdetection |  | a244af77 (2020-04-19) | 0,0% | 475 (384) | 1.855 | 496 |
| pantsbuild/pants |  | 612bd846 (2022-03-15) | 0,0% | 6.653 (4.733) | 3.894 | 7.167 |
| PrefectHQ/prefect |  | 96662782 (2020-03-18) | 0,0% | 1.592 (1.219) | 797 | 1.259 |
| pypa/pip |  | 90869935 (2014-11-20) | 0,0% | 1.095 (823) | 1.265 | 519 |
| python/typeshed |  | 1a3ae3ef (2022-09-20) | 0,0% | 5.198 (300) | 1.820 | 6.348 |
| tensorflow/models |  | b8e5a44b (2017-10-11) | 0,0% | 628 (365) | 1.509 | 576 |
| tiangolo/fastapi |  | 8cfe2544 (2020-06-05) | 0,0% | 931 (394) | 1.052 | 372 |
| JohnSnowLabs/spark-nlp |  | - | không đo được | - | - | - |

Django: số ở cột issue là ticket Trac đã sửa; Django không nhận pull request qua cơ chế merge của GitHub nên không có số PR. SymPy: số của API tìm kiếm (5.792 issue) gần khớp với dữ liệu đã cào ngày 21/10/2026 (5.785 issue). spark-nlp không clone được (lịch sử commit vượt 1,7 GB), nên không có số liệu commit và doc.

## 3. Doc

### 3.1 Cấu trúc doc và độ phủ

Cột "File doc được đọc": file `.rst`, `.md`, `.txt` trong thư mục doc (bỏ `_build`, `generated`, ...). Cột "File doc ngoài thư mục doc": file `.rst`, `.md`, `.mdx`, `.ipynb`, `.jade` ở chỗ khác, trừ `.github` và thư mục test; đề tài không đọc các file này. Cột "Đoạn doc (có cạnh)": tổng số đoạn, trong ngoặc là số đoạn có ít nhất một cạnh.

| Repo | Lite và Verified | Thư mục doc | File doc được đọc | File doc ngoài thư mục doc | Đoạn doc (có cạnh) | Cạnh nối | Hàm/lớp có doc / tổng | Độ phủ | Nguyên nhân khi dưới 5% |
|---|---|---|---|---|---|---|---|---|---|
| pyca/cryptography |  | `docs/` | 53 (52 .rst, 1 .txt) | 4 .rst (nhiều nhất ở `(gốc)`) | 385 (225) | 1.061 | 490 / 1.303 | 37,6% |  |
| pallets/flask | ✓ | `docs/` | 75 (75 .rst) | 9 .rst, 2 .md (nhiều nhất ở `(gốc)`) | 479 (138) | 253 | 97 / 405 | 24,0% |  |
| django/django | ✓ | `docs/` | 425 (424 .txt, 1 .md) | 2 .rst, 2 .md (nhiều nhất ở `(gốc)`) | 6.189 (2.303) | 5.641 | 1.623 / 9.153 | 17,7% |  |
| pydata/xarray | ✓ | `doc/` | 31 (30 .rst, 1 .txt) | 4 .md, 1 .rst (nhiều nhất ở `(gốc)`) | 627 (245) | 804 | 257 / 2.029 | 12,7% |  |
| huggingface/transformers |  | `docs/` | 64 (58 .rst, 6 .md) | 535 .md, 6 .ipynb (nhiều nhất ở `model_cards`) | 705 (417) | 568 | 466 / 3.720 | 12,5% |  |
| scikit-learn/scikit-learn | ✓ | `doc/` | 110 (106 .rst, 3 .txt, 1 .md) | 15 .rst, 3 .md (nhiều nhất ở `sklearn`) | 1.535 (667) | 2.145 | 466 / 3.925 | 11,9% |  |
| pandas-dev/pandas |  | `doc/` | 137 (136 .rst, 1 .txt) | 18 .md (nhiều nhất ở `web`) | 2.779 (694) | 2.350 | 560 / 5.861 | 9,6% |  |
| sympy/sympy | ✓ | `doc/` | 225 (224 .rst, 1 .txt) | 16 .ipynb, 4 .md, 1 .rst (nhiều nhất ở `examples`) | 1.465 (556) | 1.445 | 1.371 / 16.695 | 8,2% |  |
| mwaskom/seaborn | ✓ | `doc/` | 29 (28 .rst, 1 .md) | 2 .md (nhiều nhất ở `(gốc)`) | 162 (70) | 294 | 60 / 933 | 6,4% |  |
| astropy/astropy | ✓ | `docs/` | 277 (272 .rst, 5 .txt) | 18 .rst, 4 .md (nhiều nhất ở `licenses`) | 2.504 (412) | 827 | 460 / 8.278 | 5,6% |  |
| apache/airflow |  | `docs/` | 178 (176 .rst, 2 .txt) | 187 .md, 8 .rst, 1 .ipynb (nhiều nhất ở `airflow`) | 1.079 (306) | 409 | 366 / 6.655 | 5,5% |  |
| Lightning-AI/lightning |  | `docs/` | 31 (31 .rst) | 5 .md (nhiều nhất ở `(gốc)`) | 179 (39) | 80 | 41 / 788 | 5,2% |  |
| wagtail/wagtail |  | `docs/` | 270 (142 .md, 126 .rst, 2 .txt) | 6 .md, 1 .rst, 1 .mdx (nhiều nhất ở `(gốc)`) | 746 (28) | 293 | 277 / 6.326 | 4,4% | Nhiều tham chiếu trỏ tới thuộc tính |
| scipy/scipy |  | `doc/` | 84 (81 .rst, 3 .txt) | 1 .rst (nhiều nhất ở `(gốc)`) | 761 (135) | 262 | 183 / 4.219 | 4,3% | Doc ít so với code |
| psf/requests | ✓ | `docs/` | 15 (15 .rst) | 3 .rst (nhiều nhất ở `(gốc)`) | 106 (15) | 37 | 23 / 663 | 3,5% | Doc ít so với code |
| sphinx-doc/sphinx | ✓ | `doc/` | 83 (83 .rst) | 5 .rst (nhiều nhất ở `sphinx`) | 639 (82) | 227 | 158 / 5.007 | 3,2% | Nhiều tham chiếu không nối được |
| twisted/twisted |  | `docs/` | 149 (145 .rst, 4 .txt) | 4 .rst, 2 .md (nhiều nhất ở `(gốc)`) | 1.493 (322) | 666 | 359 / 11.490 | 3,1% | Doc ít so với code |
| pytest-dev/pytest | ✓ | `doc/` | 189 (189 .rst) | 40 .rst, 1 .md (nhiều nhất ở `changelog`) | 1.169 (98) | 182 | 138 / 4.585 | 3,0% | Doc ít so với code |
| celery/celery |  | `docs/` | 224 (215 .rst, 9 .txt) | 9 .rst (nhiều nhất ở `examples`) | 1.700 (133) | 279 | 191 / 6.569 | 2,9% | Nhiều tham chiếu không nối được (tên rút gọn `@Task.delay`) |
| gitpython-developers/GitPython |  | `doc/` | 6 (6 .rst) | 2 .md (nhiều nhất ở `(gốc)`) | 173 (15) | 32 | 20 / 689 | 2,9% | Doc ít so với code |
| matplotlib/matplotlib | ✓ | `doc/` | 362 (360 .rst, 2 .txt) | 27 .rst, 3 .md, 1 .ipynb (nhiều nhất ở `galleries`) | 2.549 (115) | 256 | 195 / 7.081 | 2,8% | `autosummary` không được đọc; nhiều tham chiếu mơ hồ |
| ipython/ipython |  | `docs/` | 79 (78 .txt, 1 .rst) | 29 .ipynb, 4 .md, 3 .rst (nhiều nhất ở `examples`) | 717 (130) | 243 | 113 / 5.110 | 2,2% | Nhiều tham chiếu không nối được |
| dagster-io/dagster |  | `docs/` | 70 (67 .rst, 3 .md) | 103 .md, 50 .ipynb, 1 .rst (nhiều nhất ở `python_modules`) | 226 (143) | 624 | 589 / 27.501 | 2,1% | Doc ít so với code |
| google/jax |  | `docs/` | 27 (26 .rst, 1 .md) | 7 .md, 4 .ipynb (nhiều nhất ở `cloud_tpu_colabs`) | 96 (18) | 57 | 46 / 2.333 | 2,0% | `autosummary` không được đọc |
| numpy/numpy |  | `doc/` | 150 (128 .rst, 22 .txt) | 0 | 1.526 (38) | 83 | 63 / 3.742 | 1,7% | `autosummary` không được đọc; nhiều tham chiếu không nối được |
| ray-project/ray |  | `doc/` | 111 (80 .rst, 29 .txt, 2 .md) | 16 .md, 15 .rst, 1 .ipynb (nhiều nhất ở `python`) | 783 (62) | 79 | 78 / 5.266 | 1,5% | Doc ít so với code |
| googleapis/google-cloud-python |  | `docs/` | 80 (69 .rst, 11 .md) | 193 .rst, 53 .md (nhiều nhất ở `spanner`) | 206 (33) | 81 | 58 / 5.596 | 1,0% | Doc ít so với code; doc từng package nằm ngoài `docs/` |
| Qiskit/qiskit |  | `docs/` | 15 (12 .rst, 3 .md) | 2 .md, 1 .rst (nhiều nhất ở `(gốc)`) | 53 (5) | 12 | 6 / 2.071 | 0,3% | Doc ít so với code |
| pylint-dev/pylint | ✓ | `doc/` | 59 (58 .rst, 1 .md) | 6 .rst, 1 .md (nhiều nhất ở `pylint`) | 291 (5) | 5 | 4 / 1.990 | 0,2% | Doc ít so với code |
| ytdl-org/youtube-dl |  | `docs/` | 3 (2 .rst, 1 .md) | 2 .md (nhiều nhất ở `(gốc)`) | 7 (2) | 2 | 2 / 4.665 | 0,04% | Doc gần như không có |
| apache/mxnet |  | `doc/` | 35 (35 .md) | 17 .md, 7 .ipynb (nhiều nhất ở `example`) | 233 (0) | 0 | 0 / 329 | 0,0% | Trang API dùng `automodule` |
| conan-io/conan |  | không có | 0 (0) | 1 .md, 1 .rst (nhiều nhất ở `(gốc)`) | 0 (0) | 0 | 0 / 2.438 | 0,0% | Không có doc trong repo |
| conda/conda |  | không có | 0 (0) | 8 .rst, 1 .md (nhiều nhất ở `conda`) | 0 (0) | 0 | 0 / 2.417 | 0,0% | Không có doc trong repo; doc ở trang ngoài |
| DataDog/integrations-core |  | `docs/` | 4 (4 .md) | 200 .md (nhiều nhất ở `mysql`) | 4 (0) | 0 | 0 / 1.266 | 0,0% | Doc Markdown |
| docker/compose |  | `docs/` | 33 (33 .md) | 9 .md (nhiều nhất ở `(gốc)`) | 33 (0) | 0 | 0 / 393 | 0,0% | Doc Markdown |
| explosion/spaCy |  | không có | 0 (0) | 146 .jade, 5 .md, 1 .rst, 1 .ipynb (nhiều nhất ở `website`) | 0 (0) | 0 | 0 / 497 | 0,0% | Doc là template `.jade` |
| jupyterlab/jupyterlab |  | `docs/` | 37 (37 .rst) | 93 .md, 7 .ipynb, 5 .rst (nhiều nhất ở `packages`) | 402 (0) | 0 | 0 / 337 | 0,0% | Doc RST viết cho phần TypeScript |
| kubeflow/pipelines |  | không có | 0 (0) | 55 .md, 21 .ipynb (nhiều nhất ở `components`) | 0 (0) | 0 | 0 / 960 | 0,0% | Không có doc trong repo; doc ở trang ngoài |
| mesonbuild/meson |  | không có | 0 (0) | 1 .md (nhiều nhất ở `(gốc)`) | 0 (0) | 0 | 0 / 1.720 | 0,0% | Không có doc trong repo |
| open-mmlab/mmdetection |  | `docs/` | 7 (6 .md, 1 .rst) | 25 .md, 1 .ipynb (nhiều nhất ở `configs`) | 13 (0) | 0 | 0 / 1.211 | 0,0% | Chỉ có trang mục lục RST |
| pantsbuild/pants |  | không có | 0 (0) | 34 .rst, 33 .md (nhiều nhất ở `src`) | 0 (0) | 0 | 0 / 8.246 | 0,0% | Không có thư mục doc ở gốc |
| PrefectHQ/prefect |  | `docs/` | 279 (279 .md) | 6 .md (nhiều nhất ở `(gốc)`) | 279 (0) | 0 | 0 / 1.398 | 0,0% | Doc Markdown |
| pypa/pip |  | `docs/` | 20 (20 .rst) | 2 .rst (nhiều nhất ở `(gốc)`) | 109 (0) | 0 | 0 / 3.332 | 0,0% | Doc RST hướng dẫn dòng lệnh |
| python/typeshed |  | không có | 0 (0) | 5 .md (nhiều nhất ở `(gốc)`) | 0 (0) | 0 | 0 / 74 | 0,0% | Không có doc; code là file stub `.pyi` |
| tensorflow/models |  | không có | 0 (0) | 104 .md, 4 .ipynb (nhiều nhất ở `research`) | 0 (0) | 0 | 0 / 5.648 | 0,0% | Chỉ có README của từng model |
| tiangolo/fastapi |  | `docs/` | 107 (107 .md) | 2 .md (nhiều nhất ở `(gốc)`) | 107 (0) | 0 | 0 / 757 | 0,0% | Doc Markdown |
| JohnSnowLabs/spark-nlp |  |  |  |  |  |  |  | không đo được | Clone vượt 1,7 GB |

### 3.2 Nguyên nhân độ phủ thấp

- **Độ phủ 0% (16 repo).** Doc không có vai trò RST hay directive nào mà cách nối nhận. 11 repo do chính repo: không có doc trong repo (conda, kubeflow/pipelines, conan, meson, pants, tensorflow/models, typeshed), doc là template `.jade` (spaCy), hoặc doc RST không nói về API Python (jupyterlab, pip, mmdetection). 5 repo do cách nối: doc viết bằng Markdown, tên code chỉ nằm trong backtick (prefect, fastapi, docker/compose, integrations-core), hoặc trang API dùng `automodule` (mxnet).
- **Độ phủ trên 0% nhưng dưới 5% (18 repo).** (1) Doc chỉ tham chiếu một phần nhỏ của code (11 repo); cách nối vẫn tốt, ví dụ twisted nối được 93% trong 818 tham chiếu nhưng có 11.490 hàm/lớp. (2) Nhiều tham chiếu không nối được (5 repo, nối được 18% đến 60%): tham chiếu tới thuộc tính, tên có trong repo nhưng không có trong graph (ví dụ `ndarray` của numpy viết bằng C), tên mơ hồ, hoặc tên của thư viện ngoài. (3) Trang API dùng `autosummary` (matplotlib, numpy, jax).

### 3.3 Mô phỏng hai thay đổi của cách nối doc

A: tham chiếu tới thuộc tính chưa nối được thì nối vào lớp cha (nếu lớp cha là Class trong graph). B: đọc các tên dưới `.. autosummary::`, nối theo đúng quy tắc hiện tại (có module ngữ cảnh). Chạy trên 38 repo có thư mục doc; bảng chỉ liệt kê repo có độ phủ tăng từ 0,05 điểm. astropy và Django chỉ thêm 1 hàm/lớp mỗi repo (dưới 0,1 điểm); các repo khác giữ nguyên.

| Repo | Lite và Verified | Trước | Sau A | Sau B | Sau A+B |
|---|---|---|---|---|---|
| numpy/numpy |  | 1,7% | 1,7% | 14,6% | 14,6% |
| pydata/xarray | ✓ | 12,7% | 12,7% | 23,4% | 23,4% |
| google/jax |  | 2,0% | 2,0% | 7,7% | 7,7% |
| matplotlib/matplotlib | ✓ | 2,8% | 2,8% | 8,0% | 8,0% |
| mwaskom/seaborn | ✓ | 6,4% | 6,4% | 10,8% | 10,8% |
| pandas-dev/pandas |  | 9,6% | 9,6% | 13,2% | 13,2% |
| scikit-learn/scikit-learn | ✓ | 11,9% | 11,9% | 13,1% | 13,1% |
| apache/mxnet |  | 0,0% | 0,0% | 0,9% | 0,9% |
| scipy/scipy |  | 4,3% | 4,3% | 4,6% | 4,6% |
| ipython/ipython |  | 2,2% | 2,3% | 2,2% | 2,3% |

Thay đổi A gần như không đổi độ phủ ở repo nào, vì lớp cha hầu như đã có cạnh. Ví dụ Django: 1.276 tham chiếu thuộc tính được nối vào lớp cha, tạo thêm 457 cạnh, nhưng độ phủ không đổi (17,7%). Thay đổi B chỉ có tác dụng ở repo dùng `autosummary`; Django và SymPy không dùng.

## 4. Commit

| Repo | Commit đầu tiên | Mọi commit tới snapshot | Commit nhánh chính | Nhánh chính, 5 năm trước snapshot | Trong đó có sửa `.py` |
|---|---|---|---|---|---|
| pyca/cryptography | 2013-08-06 | 6.944 | 2.360 | 2.360 | 1.562 |
| pallets/flask | 2010-04-06 | 4.967 | 2.056 | 576 | 292 |
| django/django | 2005-07-13 | 26.541 | 25.575 | 9.456 | 6.810 |
| pydata/xarray | 2013-09-30 | 3.473 | 2.157 | 1.651 | 1.217 |
| huggingface/transformers | 2018-10-29 | 5.098 | 3.105 | 3.105 | 2.041 |
| scikit-learn/scikit-learn | 2010-01-05 | 23.546 | 9.023 | 4.058 | 2.926 |
| pandas-dev/pandas | 2009-07-31 | 23.773 | 18.899 | 11.033 | 9.075 |
| sympy/sympy | 2007-07-19 | 30.527 | 8.466 | 3.254 | 2.915 |
| mwaskom/seaborn | 2012-06-18 | 2.998 | 1.152 | 458 | 375 |
| astropy/astropy | 2011-07-25 | 33.717 | 7.140 | 3.166 | 2.339 |
| apache/airflow | 2014-10-06 | 10.153 | 8.046 | 7.214 | 5.018 |
| Lightning-AI/lightning | 2019-03-30 | 2.459 | 1.598 | 1.598 | 1.090 |
| wagtail/wagtail | 2014-01-22 | 14.568 | 9.909 | 6.032 | 3.040 |
| scipy/scipy | 2001-02-01 | 11.488 | 7.669 | 2.598 | 2.145 |
| psf/requests | 2011-02-13 | 3.061 | 992 | 992 | 691 |
| sphinx-doc/sphinx | 2007-07-23 | 16.352 | 5.497 | 2.671 | 1.874 |
| twisted/twisted | 2001-07-09 | 28.290 | 18.642 | 675 | 573 |
| pytest-dev/pytest | 2007-01-24 | 12.321 | 5.063 | 1.927 | 1.178 |
| celery/celery | 2009-04-24 | 11.381 | 6.114 | 2.083 | 1.329 |
| gitpython-developers/GitPython | 2008-05-07 | 2.267 | 1.306 | 628 | 434 |
| matplotlib/matplotlib | 2003-05-12 | 47.501 | 16.961 | 6.675 | 5.696 |
| ipython/ipython | 2005-07-06 | 10.962 | 3.319 | 2.281 | 1.799 |
| dagster-io/dagster | 2018-04-30 | 14.501 | 14.126 | 13.989 | 9.898 |
| google/jax | 2018-11-17 | 3.712 | 1.759 | 1.759 | 1.387 |
| numpy/numpy | 2001-12-18 | 9.787 | 7.949 | 3.966 | 2.597 |
| ray-project/ray | 2016-02-07 | 4.646 | 4.402 | 4.402 | 2.875 |
| googleapis/google-cloud-python | 2014-01-28 | 6.517 | 2.999 | 2.999 | 2.553 |
| Qiskit/qiskit | 2017-03-03 | 2.635 | 1.120 | 1.120 | 939 |
| pylint-dev/pylint | 2006-04-26 | 6.540 | 5.253 | 3.102 | 2.378 |
| ytdl-org/youtube-dl | 2008-07-21 | 18.506 | 15.399 | 4.265 | 3.872 |
| apache/mxnet | 2015-04-30 | 1.858 | 532 | 532 | 210 |
| conan-io/conan | 2015-12-01 | 3.179 | 608 | 608 | 545 |
| conda/conda | 2012-10-15 | 10.710 | 3.636 | 3.454 | 2.706 |
| DataDog/integrations-core | 2015-12-01 | 2.867 | 1.180 | 1.180 | 670 |
| docker/compose | 2013-12-09 | 2.133 | 1.012 | 1.012 | 577 |
| explosion/spaCy | 2014-07-04 | 8.931 | 3.138 | 3.138 | 1.607 |
| jupyterlab/jupyterlab | 2016-01-05 | 19.819 | 3.852 | 3.852 | 617 |
| kubeflow/pipelines | 2018-05-11 | 777 | 661 | 661 | 273 |
| mesonbuild/meson | 2012-12-23 | 2.540 | 2.006 | 2.006 | 1.810 |
| open-mmlab/mmdetection | 2018-08-22 | 853 | 475 | 475 | 384 |
| pantsbuild/pants | 2011-03-16 | 11.073 | 10.833 | 6.653 | 4.733 |
| PrefectHQ/prefect | 2017-03-24 | 8.187 | 1.592 | 1.592 | 1.219 |
| pypa/pip | 2008-10-15 | 3.129 | 1.280 | 1.095 | 823 |
| python/typeshed | 2015-03-04 | 6.880 | 6.650 | 5.198 | 300 |
| tensorflow/models | 2016-01-12 | 1.302 | 628 | 628 | 365 |
| tiangolo/fastapi | 2018-12-05 | 946 | 931 | 931 | 394 |

Tổng trên 46 repo: 143.108 commit nhánh chính trong 5 năm, 98.151 commit có sửa `.py`. Với repo dùng merge commit (ví dụ twisted, SymPy), mỗi commit nhánh chính là một pull request, nên số này nhỏ hơn nhiều so với tổng số commit.

## 5. Issue và pull request

| Repo | Nguồn | Issue đã đóng trước snapshot | PR đã merge trước snapshot | Ghi chú |
|---|---|---|---|---|
| pyca/cryptography | GitHub (API tìm kiếm) | 943 | 2.437 |  |
| pallets/flask | GitHub (API tìm kiếm) | 2.464 | 1.438 |  |
| django/django | Trac (dữ liệu đã cào) | 16.189 | - | |
| pydata/xarray | GitHub (API tìm kiếm) | 2.223 | 1.964 |  |
| huggingface/transformers | GitHub (API tìm kiếm) | 4.235 | 2.117 |  |
| scikit-learn/scikit-learn | GitHub (API tìm kiếm) | 5.439 | 4.316 |  |
| pandas-dev/pandas | GitHub (API tìm kiếm) | 17.999 | 12.473 |  |
| sympy/sympy | GitHub (API tìm kiếm) | 5.792 | 4.316 |  |
| mwaskom/seaborn | GitHub (API tìm kiếm) | 2.023 | 644 |  |
| astropy/astropy | GitHub (API tìm kiếm) | 4.478 | 6.921 |  |
| apache/airflow | GitHub (API tìm kiếm) | 1.922 | 5.955 |  |
| Lightning-AI/lightning | GitHub (API tìm kiếm) | 1.047 | 869 | Tên hiện tại trên GitHub: Lightning-AI/pytorch-lightning |
| wagtail/wagtail | GitHub (API tìm kiếm) | 3.763 | 2.980 |  |
| scipy/scipy | GitHub (API tìm kiếm) | 2.466 | 860 |  |
| psf/requests | GitHub (API tìm kiếm) | 853 | 532 |  |
| sphinx-doc/sphinx | GitHub (API tìm kiếm) | 4.678 | 2.992 |  |
| twisted/twisted | GitHub (API tìm kiếm) | 7.399 | 1.274 |  |
| pytest-dev/pytest | GitHub (API tìm kiếm) | 3.691 | 2.767 |  |
| celery/celery | GitHub (API tìm kiếm) | 3.993 | 1.339 |  |
| gitpython-developers/GitPython | GitHub (API tìm kiếm) | 743 | 324 |  |
| matplotlib/matplotlib | GitHub (API tìm kiếm) | 9.001 | 14.189 |  |
| ipython/ipython | GitHub (API tìm kiếm) | 1.864 | 1.315 |  |
| dagster-io/dagster | GitHub (API tìm kiếm) | 4.296 | 7.187 |  |
| google/jax | GitHub (API tìm kiếm) | 917 | 1.234 | Tên hiện tại trên GitHub: jax-ml/jax |
| numpy/numpy | GitHub (API tìm kiếm) | 2.364 | 318 |  |
| ray-project/ray | GitHub (API tìm kiếm) | 3.537 | 4.101 |  |
| googleapis/google-cloud-python | GitHub (API tìm kiếm) | 2.379 | 3.201 |  |
| Qiskit/qiskit | GitHub (API tìm kiếm) | 906 | 1.103 |  |
| pylint-dev/pylint | GitHub (API tìm kiếm) | 3.704 | 1.751 |  |
| ytdl-org/youtube-dl | GitHub (API tìm kiếm) | 21.326 | 1.497 |  |
| apache/mxnet | GitHub (API tìm kiếm) | 219 | 372 |  |
| conan-io/conan | GitHub (API tìm kiếm) | 2.675 | 1.595 |  |
| conda/conda | GitHub (API tìm kiếm) | 4.677 | 1.246 |  |
| DataDog/integrations-core | GitHub (API tìm kiếm) | 121 | 1.107 |  |
| docker/compose | GitHub (API tìm kiếm) | 1.524 | 761 |  |
| explosion/spaCy | GitHub (API tìm kiếm) | 2.426 | 659 |  |
| jupyterlab/jupyterlab | GitHub (API tìm kiếm) | 3.828 | 3.476 |  |
| kubeflow/pipelines | GitHub (API tìm kiếm) | 473 | 703 |  |
| mesonbuild/meson | GitHub (API tìm kiếm) | 439 | 340 |  |
| open-mmlab/mmdetection | GitHub (API tìm kiếm) | 1.855 | 496 |  |
| pantsbuild/pants | GitHub (API tìm kiếm) | 3.894 | 7.167 |  |
| PrefectHQ/prefect | GitHub (API tìm kiếm) | 797 | 1.259 |  |
| pypa/pip | GitHub (API tìm kiếm) | 1.265 | 519 |  |
| python/typeshed | GitHub (API tìm kiếm) | 1.820 | 6.348 |  |
| tensorflow/models | GitHub (API tìm kiếm) | 1.509 | 576 |  |
| tiangolo/fastapi | GitHub (API tìm kiếm) | 1.052 | 372 | Tên hiện tại trên GitHub: fastapi/fastapi |

Tổng: 171.208 issue và ticket đã đóng, 119.410 pull request đã merge (tính cả SymPy theo API tìm kiếm). Số của API tìm kiếm là số hiện tại của GitHub cho các mục tạo trước ngày snapshot; mục đã bị xóa hoặc chuyển repo không được tính.

## 6. Khả năng crawl

### 6.1 Commit

| Repo | Commit thử | Thời gian mỗi commit (giây) | Trong đó lấy diff | File `.py` đổi | Hàm/lớp bị sửa |
|---|---|---|---|---|---|
| psf/requests | c93419f5 | 0,12 | 0,02 | 1 | 1 |
| psf/requests | bc34f339 | 0,96 | 0,91 | 1 | 1 |
| psf/requests | 8f0ac668 | 0,92 | 0,78 | 3 | 3 |
| psf/requests | 58bf1588 | 0,8 | 0,76 | 1 | 1 |
| psf/requests | 04770187 | 0,76 | 0,75 | 0 | 0 |
| scipy/scipy | 8741fe19 | 1,99 | 1,92 | 2 | 2 |
| scipy/scipy | 0b6efa05 | 0,88 | 0,88 | 1 | 0 |
| scipy/scipy | 2d82b665 | 0,87 | 0,82 | 1 | 0 |
| scipy/scipy | 78780a50 | 0,83 | 0,78 | 1 | 2 |
| scipy/scipy | d6eb0661 | 0,8 | 0,76 | 1 | 3 |
| pandas-dev/pandas | 6325a331 | 1,52 | 1,48 | 2 | 0 |
| pandas-dev/pandas | 7256c279 | 0,79 | 0,79 | 1 | 0 |
| pandas-dev/pandas | 07cc3bef | 0,98 | 0,86 | 1 | 1 |
| pandas-dev/pandas | 45a795e0 | 1,13 | 1,02 | 3 | 1 |
| pandas-dev/pandas | c29a2304 | 0,99 | 0,95 | 1 | 0 |

- Crawl được trên clone hiện tại (clone không kèm nội dung file). Trung bình 0,96 giây mỗi commit; gần như toàn bộ là thời gian tải nội dung file theo yêu cầu khi lấy diff. Tính hàm/lớp bị sửa chỉ thêm khoảng 0,1 giây.
- Ước tính cho 98.151 commit có sửa `.py` trong 5 năm: khoảng 26 giờ nếu chạy tuần tự trên clone hiện tại. Nếu tải toàn bộ nội dung mỗi repo một lần trước khi chạy, diff đọc từ máy và thời gian giảm nhiều; đổi lại phải tải thêm dữ liệu (chưa đo dung lượng).

### 6.2 Issue

| Nguồn | Trạng thái | Thời gian (giây) | Số mục | Trong đó là PR | Có trang sau | Lượt còn lại / giới hạn mỗi giờ |
|---|---|---|---|---|---|---|
| psf/requests, API REST 100 mục | 200 | 1,11 | 100 | 81 | có | 50 / 60 |
| scipy/scipy, API REST 100 mục | 200 | 1,1 | 100 | 85 | có | 49 / 60 |
| pandas-dev/pandas, API REST 100 mục | 200 | 1,14 | 100 | 93 | có | 48 / 60 |
| django/django (Trac), CSV 500 dòng | 200 | 0,65 | 500 | - | - | không giới hạn công bố |

- API REST trả issue và PR chung một danh sách, 100 mục mỗi trang. Tham số `page` chỉ dùng được cho 1.000 mục đầu; sau đó phải đi theo link "next" có con trỏ (đã gặp và sửa ở cell `issue-fetch`).
- Ước tính số trang để tải hết issue và PR đã đóng của các repo GitHub: khoảng 2.763 trang (chưa tính PR đóng mà không merge). Không có token, GitHub cho 60 lượt mỗi giờ, tức khoảng 46 giờ. Có token, giới hạn là 5.000 lượt mỗi giờ, tức khoảng 1 giờ.
- Trac của Django trả CSV, mỗi trang 500 ticket; đã tải đủ 19.388 ticket trong 39 trang ở lần chạy ngày 21/10/2026.

## 7. Giới hạn

- Mỗi repo chỉ đo ở một snapshot, nên độ phủ doc và số commit phản ánh trạng thái tại thời điểm đó.
- Độ phủ doc là độ phủ theo cách nối của đề tài, không phải lượng doc thật của repo.
- Số issue và PR lấy từ API tìm kiếm của GitHub ở thời điểm hiện tại; issue chuyển sang repo khác hoặc bị xóa không được tính. Số này chưa cho biết bao nhiêu issue nối được với commit.
- Thử crawl chỉ trên 15 commit và 4 trang; thời gian thực tế phụ thuộc mạng.
