# `latex_eskd`

`latex_eskd` это самостоятельный шаблон проекта на LaTeX по ЕСКД. Он собирает текстовый документ A4 с титульным листом, содержанием и штампами, отдельный чертежный лист, отдельный перечень элементов и затем склеивает все это в общий `bundle.pdf`. Титульный лист остается частью текстового документа, но в общей листности не учитывается.

Структура комплекта задается через `template_project/project_manifest.toml`. Поле `bundle.order` определяет, какие документы вообще собираются и попадают в итоговый `bundle.pdf`. В текущем варианте поддерживаются три типа документов. `text_doc` описывает текстовый документ A4 portrait. Для него поле `page_layout` в манифесте отдельно управляет оформлением страниц записки: `eskd` включает стандартные ЕСКД-штампы, `plain_frame` включает обычную прямоугольную рамку с нижней центральной нумерацией. Это поле не связано с текстом титульного листа: надпись `Курсовая работа`, `Расчетно-графическая работа` или `Лабораторная работа` по-прежнему задается в `project_meta.tex`. `drawing_doc` описывает чертежный лист с настраиваемыми форматом и ориентацией, например A3 landscape или A4 portrait, и эти параметры берутся из манифеста. `bom_doc` описывает перечень элементов, который всегда живет отдельным документом A4 portrait и генерируется из JSON.

Для текстового документа это позволяет независимо настраивать титульный лист и саму записку. Например, можно оставить на титульнике `Лабораторная работа № 3`, но включить для записки ЕСКД-штампы, или наоборот, сделать титульник `Курсовая работа`, а страницы записки оформить в обычную прямоугольную рамку.

Типовые сценарии:

```toml
# Только записка, например для лабораторной без чертежа и BOM.
[bundle]
order = ["note"]

[documents.note]
kind = "text_doc"
source = "docs/note/main.tex"
sheet_meta = "docs/note/sheet_meta.tex"
passes = 3
count_in_total = true
front_pages_excluded = 1
paper = "a4"
orientation = "portrait"
stamp_mode = "first_large_then_small"
page_layout = "plain_frame"
```

```toml
# Чертеж A4 landscape вместо A3 landscape.
[documents.drawing]
kind = "drawing_doc"
source = "docs/drawing/main.tex"
sheet_meta = "docs/drawing/sheet_meta.tex"
passes = 2
count_in_total = true
front_pages_excluded = 0
paper = "a4"
orientation = "landscape"
stamp_mode = "first"
```

Если документ убран из `bundle.order`, он не будет пересобираться и не попадет в итоговый `bundle.pdf`. Старые `docs/drawing/main.pdf` или `docs/bom/main.pdf` от предыдущих сборок могут остаться на диске, но в комплект уже не войдут.

Шаблон проекта лежит в `template_project` и устроен так:

```text
latex_eskd/
  template_project/
    build_bundle.py
    project_manifest.toml
    project_meta.tex
    eskd_meta.tex
    header_text.tex
    docs/
      note/
        main.tex
        titlepage.tex
        sections/
      drawing/
        main.tex
        fragments/
      bom/
        main.tex
        items.json
```

Рабочий сценарий простой. Достаточно скопировать `template_project` в новую папку, при необходимости поправить `project_manifest.toml`, затем заполнить `project_meta.tex`, текстовые разделы в `docs/note/sections`, чертежный фрагмент в `docs/drawing/fragments/drawing_fragment.tex` или положить рядом готовый `drawing.pdf` либо `drawing.png`, после чего заполнить `docs/bom/items.json` и запустить сборку:

```bash
cd template_project
python3 build_bundle.py
```

После сборки появятся PDF тех документов, которые включены в `bundle.order`, и общий `bundle.pdf`.

Основная настройка титульного листа и общих реквизитов делается в `project_meta.tex`. Обычно редактируются код документа, тип работы, тема, дисциплина, автор, группа, преподаватель, название вуза, кафедра, факультет, город, обозначения литер, масштаб и коды графического документа и перечня элементов. Для этого достаточно поправить такие команды:

```tex
\newcommand{\ProjectDocCode}{БЦКД.000000.000}
\newcommand{\ProjectWorkType}{Курсовая работа}
\newcommand{\ProjectLabNumber}{}
\newcommand{\ProjectTheme}{Название проекта}
\newcommand{\ProjectSubject}{Название дисциплины}
\newcommand{\ProjectAuthor}{Иванов И.И.}
\newcommand{\ProjectGroup}{ГРУППА}
\newcommand{\ProjectChecker}{Преподаватель П.П.}
\newcommand{\ProjectUniversity}{...}
\newcommand{\ProjectDepartment}{Кафедра ...}
\newcommand{\ProjectFaculty}{Факультет ...}
\newcommand{\ProjectCity}{Новосибирск}
\newcommand{\ProjectYear}{\the\year}
\newcommand{\ProjectLetterLeft}{}
\newcommand{\ProjectLetterCenter}{У}
\newcommand{\ProjectLetterRight}{}
\newcommand{\ProjectScale}{Б/М}
\newcommand{\ProjectDrawingDocType}{Э3}
\newcommand{\ProjectBOMDocType}{ПЭ3}
```

`ProjectYear` по умолчанию берется из системного времени через `\the\year`, но при желании его можно переопределить вручную. `ProjectWorkType` может быть, например, `Курсовая работа`, `Расчетно-графическая работа` или `Лабораторная работа`. Если задано `\ProjectWorkType{Лабораторная работа}` и заполнено `\ProjectLabNumber`, на титульном листе получится строка вида `Лабораторная работа № 3`. Для всех остальных типов работ `ProjectLabNumber` просто игнорируется. Оформление страниц записки при этом задается не здесь, а через `page_layout` в `project_manifest.toml`.

`build_bundle.py` сам считает листность комплекта и проставляет `Лист` и `Листов` в документах со штампами. Для текстового документа титульный лист в этот подсчет не входит. Для BOM вручную править TikZ не нужно: таблица строится из `docs/bom/items.json`. Для `drawing_doc` формат и ориентация берутся из манифеста; для `bom_doc` допустим только `A4 portrait`; для `text_doc` допустим только `A4 portrait`, а переключается только `page_layout`.
