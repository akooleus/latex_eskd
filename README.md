# `latex_eskd`

Самостоятельный шаблон проекта в LaTeX по ЕСКД:

- пояснительная записка с титульным листом и содержанием;
- лист A3 со штампом;
- перечень элементов с отлаженной геометрией таблицы;
- автоматический пересчёт `Лист/Листов`;
- сборка общего `bundle.pdf`.

Шаблон не зависит от `amplifier` и рассчитан на ручное заполнение под другую дисциплину.

## Структура

```text
latex_eskd/
  template_project/
    build_bundle.py
    project_meta.tex
    eskd_meta.tex
    header.tex
    titlepage.tex
    document.tex
    appendix_a.tex
    bom.tex
    sections/
    drawings/
    bom/
```

## Как пользоваться

1. Скопируйте `template_project` в новую папку под свой проект.
2. Заполните `project_meta.tex`.
3. Отредактируйте файлы в `sections/`.
4. Замените `drawings/drawing_fragment.tex` на свой фрагмент схемы
   или положите `drawings/drawing.pdf` / `drawings/drawing.png`.
5. Заполните `bom/bom_items.json`.
6. Соберите проект:

```bash
cd template_project
python3 build_bundle.py
```

## Что собирается

- `document.pdf` — тушка;
- `appendix_a.pdf` — лист A3;
- `bom.pdf` — перечень элементов;
- `bundle.pdf` — единый комплект.

## Замечания

- Для тушки в общей листности титульный лист не считается.
- Для A3 и BOM номера листов и `Листов` выставляются автоматически.
- BOM генерируется из `bom/bom_items.json`, TikZ руками править не нужно.
