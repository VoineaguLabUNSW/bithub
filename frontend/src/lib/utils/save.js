import streamSaver from 'streamsaver'

function createRowWriter(fileName, delim='\t') {
    const fileStream = streamSaver.createWriteStream(fileName);
    const writer = fileStream.getWriter();
    const encoder = new TextEncoder();
    return {close: writer.close.bind(writer), write: (row) => row?.length && writer.write(encoder.encode(row.join(delim) + '\n'))}
}

export { createRowWriter }