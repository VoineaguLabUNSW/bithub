"""
generate_gene_annotation.py
----------------------------
Generates a gene annotation CSV (ensembl_id → gene_symbol) from the
BrainSpan expression matrix. Run this once; the output is used by the
BrainSpanLoader to resolve gene symbol queries.

Requirements:
    pip install mygene pandas

Usage:
    python generate_gene_annotation.py \
        --expr expression.file.csv \
        --out gene_annotation.csv
"""

import argparse
import pandas as pd
import mygene

def load_ensembl_id(expr_path: str) -> list[str]:
    """Extract Ensembl gene IDs from the first column of the expression CSV."""
    gene_col = pd.read_csv(expr_path, usecols =[0])
    ids = gene_col.iloc[:,0].tolist()
    print(f"Loaded {len(ids)} Ensembl IDs from {expr_path}")
    return ids

def query_gene_symbols(ensembl_ids: list[str]) -> pd.DataFrame:
    """Query mygene.info to map Ensembl IDs to gene symbols. 
    Handles batching, duplicates and missing entries automatically. 
    """
    mg = mygene.MyGeneInfo()
    print(f"Querying mygene.info for {len(ensembl_ids)} genes...")
    results = mg.querymany(
        ensembl_ids,
        scopes="ensembl.gene",
        fields="symbol,name,entrezgene",
        species="human",
        as_dataframe=False,
        verbose=False
    )

    rows = []
    for r in results:
        rows.append({
            "ensembl_id":  r.get("query"),
            "gene_symbol": r.get("symbol"),
            "gene_name":   r.get("name"),
            "entrez_id":   r.get("entrezgene"),
            "not_found":   r.get("notfound", False)
        })

    df = pd.DataFrame(rows)
    return df

def clean_mapping(df: pd.DataFrame) -> pd.DataFrame:
    """
    Clean the raw mygene results:
    - Drop genes with no symbol found
    - Drop duplicates: if one Ensembl ID maps to multiple symbols, keep first
    - Uppercase symbols for case-insensitive matching later
    """
    # drop not-found entries
    found = df[~df["not_found"]].copy()
    not_found_count = df["not_found"].sum()

    # drop rows with null symbol
    found = found.dropna(subset=["gene_symbol"])

    # handle duplicates (one Ensembl → multiple hits) — keep first
    dupes = found["ensembl_id"].duplicated().sum()
    found = found.drop_duplicates(subset="ensembl_id", keep="first")

    # uppercase for consistent lookup
    found["gene_symbol"] = found["gene_symbol"].str.upper()

    print(f"\nMapping summary:")
    print(f"  Total queried:    {len(df['ensembl_id'].unique())}")
    print(f"  Not found:        {not_found_count}")
    print(f"  Duplicate hits:   {dupes}")
    print(f"  Final mapped:     {len(found)}")

    return found[["ensembl_id", "gene_symbol", "gene_name", "entrez_id"]]

def main():
    parser = argparse.ArgumentParser(description="Generate Ensembl→symbol gene annotation CSV")
    parser.add_argument("--expr", required=True, help="Path to BrainSpan-exp.csv")
    parser.add_argument("--out",  default="gene_annotation.csv", help="Output CSV path")
    args = parser.parse_args()

    ensembl_ids = load_ensembl_id(args.expr)
    raw          = query_gene_symbols(ensembl_ids)
    annotation   = clean_mapping(raw)

    annotation.to_csv(args.out, index=False)
    print(f"\nSaved to {args.out}")
    print(annotation.head(10).to_string(index=False))


if __name__ == "__main__":
    main()