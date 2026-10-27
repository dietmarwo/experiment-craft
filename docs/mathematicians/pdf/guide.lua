-- Adapts docs/mathematicians-guide.md for the PDF:
-- * drops the opening note that links to this PDF and its build notes;
-- * points relative repository links at the files on GitHub;
-- * keeps each code block on one page;
-- * puts wide screenshots (file names ending in -wide.png) on landscape pages
--   and bounds the height of the others.

local REPOSITORY = 'https://github.com/dietmarwo/experiment-craft/blob/main/'
local dropped = false

local function normalize(path)
  local parts = {}
  for part in path:gmatch('[^/]+') do
    if part == '..' then table.remove(parts) elseif part ~= '.' then table.insert(parts, part) end
  end
  return table.concat(parts, '/')
end

function Para(para)
  if dropped then return nil end
  local self_reference = false
  para:walk{Link = function(link)
    if link.target:match('mathematicians%-guide%.pdf$') then self_reference = true end
  end}
  if self_reference then
    dropped = true
    return {}
  end
end

function Link(link)
  local target = link.target
  if target:match('^%a[%w+.-]*:') or target:match('^#') then return nil end
  local path, fragment = target:match('^([^#]*)(#?.*)$')
  link.target = REPOSITORY .. normalize('docs/' .. path) .. fragment
  return link
end

function CodeBlock(block)
  return {pandoc.RawBlock('latex', '\\par\\noindent\\begin{minipage}{\\linewidth}'), block,
          pandoc.RawBlock('latex', '\\end{minipage}\\par\\medskip')}
end

local function wide(figure)
  local found = false
  figure:walk{Image = function(image)
    if image.src:match('%-wide%.png$') then found = true end
  end}
  return found
end

function Figure(figure)
  if wide(figure) then
    figure = figure:walk{Image = function(image)
      image.attributes.width = '22cm'
      image.attributes.height = '13.5cm'
      return image
    end}
    return {pandoc.RawBlock('latex', '\\begin{landscape}'), figure, pandoc.RawBlock('latex', '\\end{landscape}')}
  end
  return figure:walk{Image = function(image)
    image.attributes.height = '62%'
    return image
  end}
end
