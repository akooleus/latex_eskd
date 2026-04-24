# `latex_eskd`

Самостоятельный шаблон проекта в LaTeX по ЕСКД:

- текстовый документ A4 с титульным листом, содержанием и штампами;
- отдельный чертёжный лист;
- отдельный перечень элементов с отлаженной геометрией таблицы;
- автоматический пересчёт `Лист/Листов`;
- сборка общего `bundle.pdf`.

Шаблон не зависит от `amplifier` и рассчитан на ручное заполнение под другую дисциплину.

Титульный лист остаётся частью текстового документа. В общей листности он не считается,
но физически входит в итоговый PDF-комплект.

## Модель документов

Структура шаблона задаётся через `project_manifest.toml`.

Поддерживаются три базовых типа:

- `text_doc`: текстовый документ A4 portrait; первая страница после титульного листа идёт с большим штампом, следующие страницы — с малым.
- `drawing_doc`: чертёжный лист с настраиваемыми форматом и ориентацией, например A3 landscape.
- `bom_doc`: перечень элементов; всегда живёт отдельным документом A4 portrait.

## Структура

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

## Как пользоваться

1. Скопируйте `template_project` в новую папку под свой проект.
2. Отредактируйте `project_manifest.toml`, если нужно изменить состав комплекта
   или параметры отдельных документов.
3. Заполните `project_meta.tex`.
4. Отредактируйте `docs/note/sections/*`.
5. Замените `docs/drawing/fragments/drawing_fragment.tex` на свой фрагмент чертежа
   или положите рядом `docs/drawing/drawing.pdf` / `docs/drawing/drawing.png`.
6. Заполните `docs/bom/items.json`.
7. Соберите проект:

```bash
cd template_project
python3 build_bundle.py
```

## Что собирается

- `docs/note/main.pdf` — текстовый документ;
- `docs/drawing/main.pdf` — чертёжный лист;
- `docs/bom/main.pdf` — перечень элементов;
- `bundle.pdf` — единый комплект.

## Замечания

- Для `text_doc` титульный лист не считается в общей листности.
- Для документов со штампом номера листов и `Листов` выставляются автоматически.
- `bom_doc` генерируется из `docs/bom/items.json`, TikZ руками править не нужно.
