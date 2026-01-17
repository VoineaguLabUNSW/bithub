import fs from 'fs';
import path from 'path';
import { json } from '@sveltejs/kit';
import Papa from 'papaparse';

const FILES = {
  bulk: 'src/lib/data/metadata_dictionary_bulk.csv',
  sc: 'src/lib/data/metadata_dictionary_sc.csv'
};

export async function GET({ url }) {
  const mode = url.searchParams.get('mode') ?? 'bulk';
  const relPath = FILES[mode] ?? FILES.bulk;

  const filePath = path.resolve(relPath);
  const csv = fs.readFileSync(filePath, 'utf-8');

  const parsed = Papa.parse(csv, { header: true, skipEmptyLines: true });

  return json({
    mode,
    rows: parsed.data
  });
}