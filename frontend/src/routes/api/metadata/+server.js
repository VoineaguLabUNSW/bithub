import fs from 'fs';
import path from 'path';
import { json } from '@sveltejs/kit';
import Papa from 'papaparse';

export async function GET() {
  const filePath = path.resolve('src/lib/data/metadata_dictionary_bulk.csv');
  const csv = fs.readFileSync(filePath, 'utf-8');

  const parsed = Papa.parse(csv, {
    header: true,
    skipEmptyLines: true
  });

  return json(parsed.data);
}