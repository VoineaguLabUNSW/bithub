import tempfile, os, sys, csv, gzip, zlib, contextlib, itertools, re, array, io, shutil, datetime, json, struct, hashlib, math, collections.abc, logging
import oyaml, h5py, tqdm, boto3, numpy as np
import data_pb2

from typing import Callable, Iterable, Tuple, Dict, List
from unittest.mock import patch
from scipy.stats import f_oneway, spearmanr

MIN_HITS = 2
LOG2_OFFSET = 0.05
GENE_LIMIT = None
LOCAL_TMP = "tmp"

class AnnotationException(Exception):
    pass
    
def safe_access_nested(data, indices, default=None):
    for index in indices:
        if not isinstance(data, collections.abc.Sequence) or not abs(index) < len(data): return default
        data = data[index]
    return data

def manage_deploy_local(asset_paths):
    '''Return local URL mapping - local server MUST support range requests'''
    return {os.path.basename(p): os.path.join('http://localhost:5501', os.path.relpath(p, '../')) for p in asset_paths}

def calc_s3_etag(path, multipart_threshold, multipart_chunksize):
    '''Calculate hash, used to avoid re-deploying identical files'''
    with open(path, 'rb') as f:
        if os.stat(path).st_size < multipart_threshold:
            return hashlib.md5(f.read()).hexdigest()
        chunks_hashes = []
        while (chunk := f.read(multipart_chunksize)):
            chunks_hashes.append(hashlib.md5(chunk).digest())
        return hashlib.md5(b''.join(chunks_hashes)).hexdigest() + '-' + str(len(chunks_hashes))
      
def manage_deploy_cloudfront(asset_paths, cloudfront_url=None, chunk_size=8388608, prefix='bithub'):
    '''Upload list of files and return URL mapping'''
    s3 = boto3.client('s3')
    for path, name in zip(asset_paths, map(os.path.basename, asset_paths)):
        name = prefix + '/' + name
        s3_hash = None
        with contextlib.suppress(s3.exceptions.ClientError):
            s3_head = s3.head_object(Bucket='bithub-bucket', Key=name)
            s3_hash = s3_head.get('ETag')[1:-1]
            
        if not s3_hash or calc_s3_etag(path, chunk_size, chunk_size) != s3_hash:
            s3.upload_file(path, 'bithub-bucket', name, ExtraArgs={'CacheControl': 'max-age=3600'},
                           Config=boto3.s3.transfer.TransferConfig(multipart_threshold=chunk_size, multipart_chunksize=chunk_size))

    return {n: f'https://{cloudfront_url}/{prefix}/{n}' for n in map(os.path.basename, asset_paths)}

def pad_elipses(string, length=20):
    '''Transform strings to constant length in a presentable way'''
    if len(string) > length:
        return string[:length-3] + '...'
    return (' ' * (length - len(string))) + string

def calc_zscore(logs):
    log_mean = np.mean(logs)
    log_sd = np.std(logs) or 0.0000000001
    return np.array([((x - log_mean) / log_sd) for x in logs], dtype='f4')

def iterate_unique(a: Iterable, cmp_key: Callable=lambda x: x):
    '''Filter out repetitions from a sorted iterable'''
    prev_key = None
    for v in a:
        curr_key = cmp_key(v)
        if curr_key != prev_key: 
            prev_key = curr_key
            yield v

def get_matrix_name(dataset, matrix):
    '''Determine the matrix name from a path'''
    return dataset['id'] + '_' + matrix['name']
    
def open_with_progress(path, *args, **kwargs):
    '''An io.open wrapper that displays a progress bar when opened in read mode'''
    mode = args[0] if len(args) else kwargs.get('mode', 'r')
    iter = io.open(path, *args, **kwargs)
    if not kwargs.get('show_progress', True) or mode not in ['r', 'rb', 'rt']:
        return iter
    else:
        avg_bytes = (4 if mode in ['r', 'rt'] else 1)
        pbar = tqdm.tqdm(mininterval=1, desc=pad_elipses(os.path.basename(path)), total=os.path.getsize(path), unit='B', unit_scale=True, unit_divisor=1000 * avg_bytes)

        # NOTE: slower class-based monkeypatching is required for iterators (https://stackoverflow.com/a/11688033)
        class IterableWrapper:
            def __init__(self, obj):
                self.obj = obj
            
            def __next__(self):
                ret = next(self.obj)
                pbar.update(len(ret))
                return ret

            def __getattr__(self, attr):
                return getattr(self.obj, attr)

        class ParentWrapper:
            def __init__(self, obj):
                self.obj = obj
            
            def __enter__(self):
                return self

            def __exit__(self, *args, **kwargs):
                pbar.close()
                return self.obj.__exit__(*args, **kwargs)

            def read(self, *args, **kwargs):
                ret = self.obj.read(*args, **kwargs)
                pbar.update(len(ret))
                return ret
            
            def __iter__(self):
                return IterableWrapper(self.obj.__iter__())

            def __getattr__(self, attr):
                return getattr(self.obj, attr)
            
        return ParentWrapper(iter)

def count_unique(values: Iterable, limit: int):
    '''Efficiently check bounded number of unique values in an iterable'''
    s = set()
    for v in values:
        s.add(v)
        if len(s) >= limit: break
    return len(s)

def get_reorder_indices(target_order, given_order):
    '''Determine the indices to reorder any elements in given_order to target_order'''
    lookup = {}
    for i, v in enumerate(given_order): lookup[v] = i
    return [lookup.get(v, None) for v in target_order]

def apply_reorder_indices(input, buffer, steps):
    '''Apply index transformation to destination buffer'''
    for i in range(len(buffer)): buffer[i] = None
    for i, j in enumerate(steps):
        if j is not None and j < len(input): 
            buffer[i] = input[j]
    return buffer

@contextlib.contextmanager
def context_closer():
    contexts = []
    try: 
        yield contexts
    finally:
        for c in contexts: 
            c.__exit__(None, None, None)

@contextlib.contextmanager
def write_compressed_ranges(path: str):
    '''Write independently retrievable gzipped float ranges to a binary file'''
    with open(path, 'wb') as f:
        def write_row(binary):
            start = f.tell()
            f.write(zlib.compress(binary, level=-1))
            return start, f.tell()
        yield write_row, f.tell

@contextlib.contextmanager
def read_compressed_ranges(path: str):
    '''Read independently retrievable gzipped float ranges from a binary file'''
    with open_with_progress(path, 'rb') as f:
        def read_row(start, end, row_length):
            f.seek(start)
            return zlib.decompress(f.read(end - start))
        yield read_row

@contextlib.contextmanager
def iterate_csv(path: str, strip_numeric: bool=False, comment=None, skip=0, delimiter=',', csv_kwargs={}, file_kwargs={}):
    '''Iterate over a CSV file, optional .gz, optional leading numeric column'''
    csv_kwargs = {**csv_kwargs, 'delimiter': delimiter}
    with gzip.open(path, mode='rt', newline='') if path.endswith('.gz') else open(path,  mode='r', newline='', **file_kwargs) as f:
        rows = csv.reader(f, **csv_kwargs)
        if comment: rows = filter(lambda row: not row or not row[0].startswith(comment), rows)
        if skip: rows = itertools.islice(rows, skip, None)
        headers, ret = [], []
        try:
            headers = next(rows)
            second = next(rows)
            if len(headers) == len(second): 
                headers = headers[1:]

            offset = 2 if second[0].isdigit() and strip_numeric else 1
            headers = headers[offset-1:]
            ret = itertools.chain([second[offset-1:]], map(lambda row: row[offset-1:], rows))
        except StopIteration:
            pass
        yield headers, ret

@contextlib.contextmanager
def iterate_csv_sorted(path: str, strip_numeric: bool=False, comment: str=None, skip: int=0, delimiter: str=',', mutator: Callable=None, csv_kwargs={}, file_kwargs={}, use_cache=True, create_cache=True):
    '''Iterate over a CSV file, optionally gzipped, annotated by annotator function'''
    with tempfile.TemporaryDirectory(dir=os.path.abspath(LOCAL_TMP)) as tmpdirname:
        cache_path = os.path.join(os.getcwd(), 'cache', os.path.basename(path) + '.sorted_cache')
        sort_path = os.path.join(tmpdirname, f'sort_{os.path.basename(path)}')
        if use_cache and os.path.exists(cache_path):
            logging.info(f're-run and delete cache folder {cache_path} to see annotation errors in this log')
            sort_path = cache_path
        else:
            # Initial mutation pass if necessary
            pre_sort_path = path
            if strip_numeric or skip or comment or mutator:
                pre_sort_path = os.path.join(tmpdirname, f'annot_{os.path.basename(path)}')
                with open(os.path.join(tmpdirname, pre_sort_path), 'w') as f:
                    writer = csv.writer(f, **csv_kwargs)
                    with iterate_csv(path,  strip_numeric=strip_numeric, delimiter=delimiter, skip=skip, comment=comment, csv_kwargs=csv_kwargs, file_kwargs=file_kwargs) as reader:
                        headers, rows = reader

                        writer.writerow([''] + headers)
                        for row in rows:
                            if not row: continue
                            if mutator:
                                try:
                                    mutator(row)
                                except AnnotationException as e:
                                    logging.warning(f'{path}\t{str(e)}')
                                    continue
                            writer.writerow(row)

            # Fast out-of-memory sort
            os.system(f'(head -n 1 {pre_sort_path} && tail -n +2 {pre_sort_path} | sort) | tr -d \'\\r\' > {sort_path}')
            if (pre_sort_path != path): os.remove(pre_sort_path)

            if create_cache: 
                os.makedirs(os.path.dirname(cache_path), exist_ok=True)
                os.rename(sort_path, cache_path)
                sort_path = cache_path

        with iterate_csv(sort_path, csv_kwargs=csv_kwargs, file_kwargs=file_kwargs) as reader:
            yield reader

def get_biomart_annotator(path: str):
    '''Create a function that returns the gene symbol, start, and end of a gene given a gene name or transcript ID'''
    get_data = {}
    with iterate_csv(path, delimiter='\t') as reader:
        _, rows = reader
        prev = None
        for row in rows:
            if row[0] != prev: 
                # ID, symbol, start, end
                data = (row[0], row[13], int(row[5]), int(row[6]))
                get_data[row[0]] = data
                get_data[row[4]] = data
                prev = row[0]
                
    return lambda gene: get_data.get(gene, None)

def get_ncbi_annotator(gene_info_path: str, gtf_path: str, gene_alias_path: str):
    gene_to_gene = {}
    transcript_to_gene = {}
    transcript_to_transcript = {}

    # Use GTF as primary annotation source
    with iterate_csv(gtf_path, delimiter='\t', strip_numeric=False, comment='#!', file_kwargs=dict(encoding='ascii')) as reader:
        transcript_to_gene_id = {}
        _, rows = reader
        CHR_WHITELIST = ['X', 'Y', 'MT']
        for row in rows:
            if row[2] == 'gene':
                id = re.search(r'gene_id "([A-Z0-9]+)"', row[8])
                name = re.search(r'gene_name "([A-Z0-9]+)"', row[8])
                if id and name and (row[0].isnumeric() or row[0] in CHR_WHITELIST):
                    id, name = id.group(1), name.group(1)
                    gene_to_gene[id] = [id, name, row[0], int(row[3]), int(row[4]), row[6], '-']
            elif row[2] in ['transcript']:
                id = re.search(r'gene_id "([A-Z0-9]+)"', row[8])
                transcript_id = re.search(r'transcript_id "([A-Z0-9]+)"', row[8])
                if id and transcript_id:
                    transcript_to_transcript[transcript_id.group(1)] = int(transcript_id.group(1)[4:])
                    transcript_to_gene_id[transcript_id.group(1)] = id.group(1)

        # Add transcripts to main lookup
        for transcript_id, gene_id in transcript_to_gene_id.items(): 
            gene_obj = gene_to_gene.get(gene_id, None)
            if gene_obj: transcript_to_gene[transcript_id] = gene_obj

    # Get descriptions
    with iterate_csv(gene_info_path, delimiter='\t', strip_numeric=False, file_kwargs=dict(encoding='ascii')) as reader:
        _, rows = reader
        for row in rows:
            id = re.search(r'Ensembl:([A-Z0-9]+)', row[5])
            if id:
                data = gene_to_gene.get(id.group(1), None)
                if data:
                    if row[8]: 
                        data[6] = row[8][0].capitalize() + row[8][1:] 

    # Get aliase / old names
    with iterate_csv(gene_alias_path, delimiter='\t', strip_numeric=False, file_kwargs=dict(encoding='utf8')) as reader:
        _, rows = reader
        for row in rows:
            if row[5] and (data := gene_to_gene.get(row[5], None)):
                    for alias in (row[1] + ',' + row[3] + ',' + row[4]).split(','):
                        if alias and (alias := alias.strip()): 
                            gene_to_gene.setdefault(alias, data)

    return gene_to_gene, transcript_to_transcript, transcript_to_gene

def accumulate_iterator(iterator, acc_key):
    '''Group consecuative identical keys into a single (group_key, [members])'''
    acc_group_key = None
    acc_group = []
    for val in iterator:
        acc_val = acc_key(val)
        if acc_group and acc_val != acc_group_key: 
            yield acc_group_key, acc_group
            acc_group.clear()
        acc_group.append(val)
        acc_group_key = acc_val
    yield acc_group_key, acc_group

def parallel_iterator(iterators, sort_key, debug=False):
    '''Iterate sparsely over multiple sorted iterators in parallel, yielding tuples of shared (group_key, [members])'''    
    group_sort_func = lambda g: g[1]
    group_create_func = lambda i, v: (i, sort_key(v), v) if v else None 
    
    latest = [group_create_func(i, next(it, None)) for i, it in enumerate(iterators)]

    while any(latest): 
        min_group = min((g for g in latest if g), key=group_sort_func)
        min_group_key = min_group[1]
        min_groups = [g if (g and ((g[1]) == min_group_key)) else None for g in latest]
        min_vals = [g[2] if g else None for g in min_groups]

        yield (min_group_key, min_vals)

        for g in min_groups:
            if g is not None:
                latest[g[0]] = group_create_func(g[0], next(iterators[g[0]], None))

@contextlib.contextmanager
def parallel_matrix_context(dataset, mutator, debug=False):
    '''Iterate over a dataset's matrices, yielding tuples of (gene name, (matrix name, sample names, gene name, expression values))'''

    with context_closer() as contexts:
        sorted_iters, sorted_headers = [], []
        for matrix in dataset['matrices']:
            # Iterate sorted (by first real column / gene ID)
            contexts.append(iterate_csv_sorted(os.path.join(dataset['dir'], matrix['path']), mutator=mutator, delimiter=',', strip_numeric=True))
            headers, rows = contexts[-1].__enter__()

            # Add extra info to rows (NOTE: nesting/parameter needed to avoid shared state)
            def _iter(dataset, matrix, rows, headers):
                for row in iterate_unique(rows, lambda x: x and x[0]): 
                    yield (dataset, matrix, headers, row[0], row[1:])
                    logging.debug(f'{matrix["name"]} yielded {row[0]}')
            
            sorted_iters.append(_iter(dataset, matrix, rows, headers))
            sorted_headers.append(headers)

        # Iterator yields tuples of (gene name, (matrix name, sample names, gene name, expression values))
        yield sorted_headers, parallel_iterator(sorted_iters, lambda v: v[3])

@contextlib.contextmanager
def parallel_transcript_iterator(dataset, transcript_to_gene):
    '''Iterate over transcripts grouped by gene'''
    def transcript_row_mutator(row):
        versionless = row[0].split('.', 1)[0]
        if annot := transcript_to_gene.get(versionless, None):
            row[0] = versionless
            row.insert(0, annot[0])
        else:
            raise AnnotationException(f'failed to annotate\ttranscript\t{row[0]}')

    with context_closer() as contexts:
        sorted_iters, sorted_headers = [], []
        for matrix in dataset.get('transcript_matrices', []):
            contexts.append(iterate_csv_sorted(os.path.join(dataset['dir'], matrix['path']), strip_numeric=True, mutator=transcript_row_mutator))
            headers, rows = contexts[-1].__enter__()

            sorted_iters.append(accumulate_iterator(rows, lambda row: row[0]))
            sorted_headers.append(headers)

        yield sorted_headers, parallel_iterator(sorted_iters, lambda x: x[0])

@contextlib.contextmanager
def parallel_dataset_context(datasets, gene_to_gene, transcript_to_gene, debug=False):
    def gene_row_mutator(row):
        versionless = row[0].split('.', 1)[0]
        if annot := gene_to_gene.get(versionless, None):
            row[0] = annot[0]
        else:
            raise AnnotationException(f'failed to annotate\tgene\t{row[0]}')

    with context_closer() as contexts:
        firsts, yields = [], []
        for d in datasets:
            # Get (headers, iterator) for each matrix set
            contexts.append(parallel_matrix_context(d, gene_row_mutator, debug=debug))
            matrix_iterator = contexts[-1].__enter__()

            # Get (headers, iterator) for variance partition
            variance_iterator = [None, iter([])]
            if varpart_path := d.get('variancePartition', None):
                contexts.append(iterate_csv_sorted(os.path.join(d['dir'], varpart_path), mutator=gene_row_mutator, strip_numeric=True))
                variance_iterator = contexts[-1].__enter__()

            # Get (headers, iterator) for transcript matrix
            transcript_iterator = [None, iter([])]
            if 'transcript_matrices' in d:
                contexts.append(parallel_transcript_iterator(d, transcript_to_gene))
                transcript_iterator = contexts[-1].__enter__()

            firsts.append([variance_iterator[0], matrix_iterator[0], transcript_iterator[0]])
            yields.append(parallel_iterator([variance_iterator[1], matrix_iterator[1], transcript_iterator[1]], lambda kv: kv[0]))

        yield firsts, parallel_iterator(yields, lambda kv: kv[0], debug=debug)

def parse_metadata(dataset, order_entries: Dict[str, List[str]], category_limit: int=50):
    column_types = {}
    if annot := dataset.get('annot', None):
        with iterate_csv(os.path.join(dataset['dir'], annot), delimiter=',', csv_kwargs={}) as reader:
            _, rows = reader
            for row in rows: 
                if len(row) == 4 and row[2] == 'Yes':
                    column_types[row[1]] = row[3]

    # Iterate sorted (by first real column i.e. sample name)
    with iterate_csv_sorted(os.path.join(dataset['dir'], dataset['meta']), delimiter=',', strip_numeric=True) as reader:
        top_headers, rows = reader
        row_list = list(rows)
        side_headers = [r[0] for r in row_list]

        top_headers_enum = list(enumerate(top_headers))
        filter_factors_enum = None
        if customFilter := dataset.get('customFilter', None):
            h = customFilter['column']
            i = top_headers.index(h)
            categories, factors = np.unique([r[1+i] for r in row_list], return_inverse=True)
            filter_factors_enum = (h, [str(c) for c in categories], factors)
            
        # Parse columns into separate typed np arrays
        def columns():
            for i, h in top_headers_enum:
                column = convert_to_serializable([r[1+i] for r in row_list])
                attrs = {}
                if column.dtype.type is not np.bytes_ or count_unique(column, category_limit) < category_limit:
                    order_entry = next((o for o in order_entries if o['variable'] == h), None)
                    if order_entry:
                        attrs['order'] = order_entry['order']
                        if groups := order_entry.get('groups', None):
                            attrs['groupSizes'] = list(map(lambda x: x['size'], groups))
                            attrs['groupLabels'] = list(map(lambda x: x['label'], groups))
                    groups = None
                    yield h, column, groups, attrs, column_types.get(h, None)

        return top_headers, side_headers, filter_factors_enum, columns()

def write_metadata_columns(hdf5_f, columns: Iterable[Tuple[str, np.ndarray, Dict[str, List[str]]]], extra_attrs={}):
    '''Write each column as a separate dataset since JS struggles to deserialize different types'''
    sample_root = hdf5_f.create_group('samples')
    column_headers, column_types = [], []
    for header, array, groups, attrs, col_type in columns:
        if header in column_headers: continue
        column_headers.append(header)
        column_types.append(col_type)
        ds = sample_root.create_dataset(header, data=array, chunks=array.shape, compression='gzip', compression_opts=9)
        for k, v in (attrs).items():
            ds.attrs.create(k, v)
    sample_root.attrs['order'] = column_headers
    for k, v in (extra_attrs).items():
        sample_root.attrs.create(k, v)
    
    # Only write types if some are actually defined
    if column_types.count(None) < len(column_types):
        for i, t in enumerate(column_types):
            if t is None: column_types[i] = 'Uncategorized'
        sample_root.attrs['type'] = column_types

def convert_to_serializable(values: Iterable, force_string=False, na_values=['NA', '']):
    '''HDF5 does not support unicode, but otherwise try to use numpy auto-typing'''
    arr = None

    if not force_string:
        converters = [int, float]
        for i in range(len(values)):
            if values[i] in na_values: 
                values[i] = np.nan
            else:
                for f in converters:
                    try: values[i] = f(values[i])
                    except ValueError: continue
                    else: break
        arr = np.array(values)
        
    if force_string or arr.dtype.char == 'U':
        values = ['Unknown' if v is np.nan else str(v) for v in values]
        max_len = 0 if not values else max(map(len, values))
        arr = np.array([v.encode() for v in values], dtype=f'S{max_len}')
    return arr

def write_string_dataset(hdf5_f, name: str, values: Iterable[str]):
    '''Write a string dataset with correct encoding'''
    hdf5_f.create_dataset(name, data=convert_to_serializable(values, force_string=True), compression='gzip', compression_opts=9)

def test_parallel_iteration():
    '''Basic sanity check for parallel iteration'''
    first = [1, 2, 3, 4]
    second = [1, 3]
    result = list(parallel_iterator([iter(first), iter(second)], lambda x: x))

    assert len(result) == 4
    assert len(result[2]) == 2
    assert result[1][1] == [2, None]

    first = [1, 2, 3, 4]
    second = [1, 2, 3, 4]
    result = list(parallel_iterator([iter(first), iter(second)], lambda x: x))
    assert len(result) == 4
    assert len(result[2]) == 2
    assert result[1][1] == [2, 2]

def test_accumulate_iteration():
    test = [1, 1, 5, 5, 3, 3]
    result = [(k,[*v]) for k,v in accumulate_iterator(iter(test), lambda x: x)]
    assert len(result) == 3
    assert result[0] == (1, [1, 1])

def test_reorder():
    '''Basic sanity check for reordering'''
    target = ['z', 'b', 'c', 'a']
    given = ['b', 'a', 'c', 'z']
    buffer = [None] * len(target)
    
    steps = get_reorder_indices(target, given)
    fixed = apply_reorder_indices(given, buffer, steps)
    assert fixed == target

def test_reorder_missing():
    '''Basic sanity check for reordering'''
    target = ['z', 'b', 'c', 'a']
    given = ['b', 'a', 'c']
    buffer = [None] * len(target)
    
    steps = get_reorder_indices(target, given)
    fixed = apply_reorder_indices(given, buffer, steps)
    assert fixed == [None, 'b', 'c', 'a']

    target = ['b', 'a', 'c']
    given = ['z', 'b', 'c', 'a']
    buffer = [None] * len(target)
    
    steps = get_reorder_indices(target, given)
    fixed = apply_reorder_indices(given, buffer, steps)
    assert fixed == ['b', 'a', 'c']

def test_compressed_ranges():
    '''Basic sanity check for compressed ranges'''
    with tempfile.TemporaryDirectory() as tmpdirname:
        path = os.path.join(tmpdirname, 'binary.bin')
        ranges = []
        data = list(range(10000))
        with write_compressed_ranges(path) as writer_utils:
            writer, teller = writer_utils
            for _ in range(20):
                row = data_pb2.RowData()
                row.values.extend(data)
                ranges.append(writer(row.SerializeToString()))
        with read_compressed_ranges(path) as reader:
            for r in ranges:
                row = data_pb2.RowData()
                row.ParseFromString(reader(*r, 10000))
                for i, v in enumerate(row.values):
                    assert v == data[i]

def run():
    if len(sys.argv) != 2 or sys.argv[1] in ('-h', '--help'): 
        print("Error: First argument should be input.yaml path, see example")
        exit(1)
        
    with patch('builtins.open', open_with_progress):
        test_parallel_iteration()
        test_accumulate_iteration()
        test_reorder()
        test_reorder_missing()
        test_compressed_ranges()

        total_written = 0
        
        # Read file locations and metadata from input YAML
        inputObj = None
        with open(sys.argv[1], 'r') as stream:
            try:
                inputObj = oyaml.safe_load(stream)    
            except oyaml.YAMLError as e:
                raise Exception('Error reading YAML input') from e
            
        OUTPUT_FOLDER = inputObj['output_external']
        OUTPUT_RESOURCES = inputObj['output_resources']
        EXPRESSION_PATH = os.path.join(OUTPUT_FOLDER, 'expression.bin')

        for p in [OUTPUT_FOLDER, OUTPUT_RESOURCES, LOCAL_TMP]:
            os.makedirs(p, exist_ok=True)
            
        log_num, log_path = 0, None
        while os.path.exists(log_path := os.path.join(OUTPUT_FOLDER, f'warnings{("." + str(log_num)) if log_num else ""}.log')): 
            log_num += 1

        logging.basicConfig(filename=log_path,
                            filemode='w',
                            format='%(asctime)s,bithub,%(levelname)s\t%(message)s',
                            datefmt='%H:%M:%S',
                            level=logging.INFO)
        
        def deploy(paths):
            return manage_deploy_local(paths) if inputObj['deploy_local'] else manage_deploy_cloudfront(paths, inputObj['deploy_url'])

        if inputObj.get('deploy_only', False):
            deploy([os.path.join(OUTPUT_FOLDER, p) for p in os.listdir(OUTPUT_FOLDER)])
            exit(0)

        # Load gene mappings/annotations into memory
        gene_to_gene, transcript_to_transcript, transcript_to_gene = get_ncbi_annotator(inputObj.get('ncbi_gene_info', None), inputObj.get('ncbi_gtf'), inputObj.get('genenames_alias', None))
        all_ranges = []

        with h5py.File(os.path.join(OUTPUT_FOLDER, 'out.hdf5'), 'w') as root, open(os.path.join(OUTPUT_FOLDER, 'errors.tsv'), 'w') as f_err:
            with context_closer() as contexts:
                contexts.append(write_compressed_ranges(EXPRESSION_PATH))
                writer, teller = contexts[-1].__enter__()
                last_range_end = 0

                # Iterate over all annotated genes in all datasets in alphanumeric order
                annots_written = []
                with parallel_dataset_context(inputObj['datasets'], gene_to_gene, transcript_to_gene) as ret:
                    first, iterator = ret
                    all_metadata_columns = {}

                    meta_root = root.create_group('metadata')
                    for dataset, headers in zip(inputObj['datasets'], first):

                        variance_headers, matrix_headers, transcript_headers = headers
                        dataset['_internal'] = ([], [0], [], variance_headers)

                        # Get sample order from metadata first column
                        orders = [o for o in inputObj['customMetadataCategoryOrders'] if dataset['id'] in o['datasets']]
                        top_headers, side_headers, filter_factors_enum, columns = parse_metadata(dataset, orders)
                        
                        samples_from_metadata = list(iterate_unique(side_headers))

                        data_meta_root = meta_root.create_group(dataset['id'])

                        # Write display-related settings
                        extra_attrs = {}
                        if custom_filter := dataset.get('customFilter', None):
                            extra_attrs['customFilterCategory'] = filter_factors_enum[1]
                            if name_filter := custom_filter.get('name', None):
                                extra_attrs['customFilterName'] = name_filter.strip()
                            if order_filter := custom_filter.get('column', None):
                                extra_attrs['customFilterColumn'] = order_filter.strip()
                        if column_default := dataset.get('default', None):
                            extra_attrs['customDefaultColumn'] = column_default

                        # Determine minimal sample set to write
                        samples_from_matrices = set()
                        for samples in matrix_headers:
                            samples_from_matrices.update(samples)
                        sample_whitelist = samples_from_matrices.intersection(samples_from_metadata)
                        sample_whitelist_ordered = list(sorted(sample_whitelist))
                        
                        # Store sample metadata in memory for pvalue calculations
                        column_indices = list(filter(lambda x: x is not None, get_reorder_indices(sample_whitelist_ordered, side_headers)))
                        def filter_metadata(columns):
                            new_array = columns[1][column_indices]
                            new_groups = [np.where(new_array == c)[0] for c in set(new_array)] if new_array.dtype.type is np.bytes_ else None
                            return (columns[0], new_array, new_groups, columns[3], columns[4])
                        all_metadata_columns[dataset['id']] = (list(map(filter_metadata, columns)), extra_attrs)
                        
                        # Write sample names
                        with contextlib.suppress(Exception):
                            write_string_dataset(data_meta_root, 'sample_names', sample_whitelist_ordered)
                        dataset['_internal_sample_count'] = len(sample_whitelist)
                        dataset['_null_transcripts'] = [None] * len(dataset.get('transcript_matrices', []))
                        
                        for matrix, samples in zip(dataset['matrices'], matrix_headers):
                            ranges, logs, pvalue_ranges = [], [], []
                            # Initialize re-order buffer
                            reorder_indices = get_reorder_indices(sample_whitelist_ordered, samples)
                            reorder_buffer = [None] * len(sample_whitelist_ordered)

                            # Create fixed filter indices
                            logs_filter_enum = None
                            if filter_factors_enum:
                                filter_name, filter_categories, filter_factors = filter_factors_enum
                                filter_indices = [[] for _ in filter_categories]
                                for i, fv in enumerate(apply_reorder_indices(filter_factors, reorder_buffer, reorder_indices)):
                                    if fv is not None: filter_indices[fv].append(i)
                                logs_filter_enum = (filter_factors_enum, filter_indices, [[] for _ in filter_factors_enum[1]])

                            matrix['_internal'] = (ranges, reorder_indices, reorder_buffer, logs, logs_filter_enum, pvalue_ranges)

                        if not (transcript_matrices := dataset.get('transcript_matrices', None)): continue
                        
                        for transcript, categories in zip(transcript_matrices, transcript_headers):
                            order_entry = next((o for o in orders if o['variable'] == transcript.get('variable', None)), None)
                            if order_entry: categories = [k for k in order_entry['order'] if k in categories]
                            else: categories = categories[1:]
                            transcript['_internal'] = ([], categories)

                    # Loop over all genes
                    VARPART_INDICES, MATRIX_INDICES, TRANSCRIPT_INDICES = (1, 0), (1, 1, 1), (1, 2, 1)
                    for gene, combined in itertools.islice(iterator, GENE_LIMIT):

                        # N.B. verify using json.dump with default - combining parallel primitives leads to lots of nested keys
                        varparts_per_dataset = tuple(safe_access_nested(c, VARPART_INDICES, None) for c in combined)
                        m_groups_per_dataset = tuple(safe_access_nested(c, MATRIX_INDICES, None) for c in combined)
                        t_groups_per_dataset = tuple(safe_access_nested(c, TRANSCRIPT_INDICES, None) for c in combined)                   

                        if not (annot := gene_to_gene.get(gene, None)):
                            raise AnnotationException(f'unexpected gene {gene} - annotation/sorted cache likely outdated')
                        
                        if MIN_HITS > (len(m_groups_per_dataset) - m_groups_per_dataset.count(None)): 
                            which_ds = [inputObj['datasets'][mi]['id'] for mi, m in enumerate(m_groups_per_dataset) if m is not None]
                            logging.warning(f'pipeline\tonly in {",".join(which_ds)}\tgene\t{gene}')
                            continue

                        annots_written.append(annot)
                        total_written += 1
                        for dataset, varpart, matrices, transcripts in zip(inputObj['datasets'], varparts_per_dataset, m_groups_per_dataset, t_groups_per_dataset):
                            # Maintain sparse lookup indices for each dataset
                            indices, curent_index, varpart_ranges, varpart_headers = dataset['_internal']
                            indices.append(curent_index[0] if matrices else -1)
                            
                            # Drop anything that doesn't appear in all matrices so we don't need to manage a second index
                            if not matrices or not all(matrices): continue

                            curent_index[0] += 1
                            if varpart_headers:
                                row = data_pb2.RowData()
                                row.values.extend([float(v) for v in varpart[1:]] if varpart else [0.0] * len(varpart_headers))
                                varpart_ranges.append(writer(row.SerializeToString()))

                            for m in matrices:
                                if m is None: continue
                                dataset, matrix, samples, gene, values = m
                                ranges, reorder_indices, reorder_buffer, logs, logs_filter_enum, pvalue_ranges = matrix['_internal']

                                # Write re-orderd matrix row and save range (input, buffer, steps)
                                fixed = apply_reorder_indices([float(v) for v in values], reorder_buffer, reorder_indices)
                                
                                # Calculate pvalues for each column against expression data
                                pvalues = []
                                for header, array, groups, attrs, col_type in all_metadata_columns[dataset['id']][0]:
                                    if not groups:
                                        pvalues.append(spearmanr(fixed, array, nan_policy='omit')[1])
                                    elif len(groups) == 1:
                                        pvalues.append(float('nan'))
                                    else:
                                        pvalues.append(f_oneway(*[[fixed[i] for i in g] for g in groups], nan_policy='omit')[1])
                                pvalue_row = data_pb2.RowData()
                                pvalue_row.values.extend(pvalues)
                                pvalue_ranges.append(writer(pvalue_row.SerializeToString()))
                                
                                row = data_pb2.RowData()
                                row.values.extend(fixed)
                                ranges.append(writer(row.SerializeToString()))

                                # Get logs for zscore calc
                                fixed_logged = [math.log2(abs(v) + LOG2_OFFSET) for v in fixed]
                                logs.append(np.mean(fixed_logged))
                                
                                # Determine region subset
                                if logs_filter_enum:
                                    _, filter_indices, logs_filter = logs_filter_enum
                                    for i in range(len(filter_indices)):
                                        logs_filter[i].append(np.mean([fixed_logged[j] for j in filter_indices[i]]))
                                        
                            if 'transcript_matrices' in dataset:
                                for transcript_matrix, accumulated in zip(dataset['transcript_matrices'], transcripts or dataset['_null_transcripts']):
                                    ranges, categories = transcript_matrix['_internal']
                                    table = data_pb2.TableData()
                                    if accumulated is not None: 
                                        _, t_list = accumulated
                                        for t in t_list:
                                            _, transcript_id, *vals = t
                                            table.float_values.extend([float(v) for v in vals])
                                            table.string_values.append(transcript_id)
                                    ranges.append(writer(table.SerializeToString()))
                    
                    # Write metadata columns and their pvalues
                    for dataset_id, [columns, extra_attrs] in all_metadata_columns.items():
                        write_metadata_columns(meta_root[dataset_id], columns, extra_attrs)
                        
                all_ranges.append((last_range_end, teller()))

            logging.info(f'processed {total_written} entries')

            # Point to which datasets need to be pulled
            remote_range_datasets = []

            # Finally, write main table and matrix compressed ranges
            data_root = root.create_group('data')
            
            display_settings = [
                # (visible, searchable, is_database, is_dataset, is_brain_dataset, associated column)
                (1, 1, 0, 0, 0, 'Ensembl ID'),
                (1, 1, 0, 0, 0, 'Gene Symbol'),

                (0, 0, 0, 0, 0, 'Gene Description'),
                (0, 0, 0, 0, 0, 'chr'),
                (0, 0, 0, 0, 0, 'hg38 start'),
                (0, 0, 0, 0, 0, 'hg38 end'),
            ]

            def boolean_to_indices(values):
                return [i for i, v in enumerate(values) if v]

            write_string_dataset(data_root, 'Ensembl ID', [a[0] for a in annots_written])
            write_string_dataset(data_root, 'Gene Symbol', [a[1] for a in annots_written])
            write_string_dataset(data_root, 'Gene Description', [a[6] for a in annots_written])
            write_string_dataset(data_root, 'chr', [a[2] for a in annots_written])
            data_root.create_dataset('hg38 start', data=[a[3] for a in annots_written], compression='gzip', compression_opts=9)
            data_root.create_dataset('hg38 end', data=[a[4] for a in annots_written], compression='gzip', compression_opts=9)

            url_root = root.create_group('urls')
            for d in inputObj['datasets']:
                display_settings.append((1, 0, 0, 1, 1, d['id']))

                # Add main lookup indices to data table
                indices, *_ = d['_internal']
                data_root.create_dataset(d['id'], data=indices, compression='gzip', compression_opts=9)

                # Write url (NOTE: individual URLs no longer supported)
                curr_url_root = url_root.create_dataset(d['id'], data=h5py.Empty('S1'))
                curr_url_root.attrs.create('home', d.get('url', ''))

            data_root.attrs.create('coordinateIndices', [3, 4, 5])
            data_root.attrs.create('order', [s[5] for s in display_settings])
            data_root.attrs.create('defaultVisible', boolean_to_indices([s[0] for s in display_settings]))
            data_root.attrs.create('defaultSearchable', boolean_to_indices([s[1] for s in display_settings]))
            data_root.attrs.create('isDatabase', [s[2] for s in display_settings])
            data_root.attrs.create('isDataset', [s[3] for s in display_settings])
            data_root.attrs.create('isBrainDataset', [s[4] for s in display_settings])

            pg_root = root.create_group('groups')
            pg_root.attrs.create('order', [pg['id'] for pg in inputObj['groups']])

            for pg in inputObj['groups']:
                p_pg_root = pg_root.create_group(pg['id'])

                # Internally hard-link datasets inside relavent groups
                for d_id in pg['datasets']:
                    with contextlib.suppress(KeyError):
                        p_pg_root[d_id] = root['metadata'][d_id]

            asset_urls = deploy([EXPRESSION_PATH])
            expression_url = asset_urls.get(os.path.basename(EXPRESSION_PATH), '')

            for d in inputObj['datasets']:
                meta_root = root['metadata'][d['id']]
                matrix_meta_root = meta_root.create_group('matrices')
                matrix_meta_root.attrs.create('order', [m['name'] for m in d['matrices']])
                all_logs = {}
                [filter_name, filter_categories] = ['', []]
                for matrix in d['matrices']:
                    name, shape = matrix['name'], (len(annots_written), d['_internal_sample_count'])
                    ranges, _, _, logs, logs_filter_enum, pvalue_ranges = matrix['_internal']
        
                    curr_matrix_meta_root = matrix_meta_root.create_dataset(name, data=ranges, compression='gzip', compression_opts=9)
                    curr_matrix_meta_root.attrs.create('path', expression_url)
                    curr_matrix_meta_root.attrs.create('shape', shape)
                    remote_range_datasets.append([curr_matrix_meta_root.name, '/data/' + d['id'], 'RowData'])
                    
                    curr_matrix_pvalue_root = matrix_meta_root.create_dataset(name + '_pvalues', data=pvalue_ranges, compression='gzip', compression_opts=9)
                    remote_range_datasets.append([curr_matrix_pvalue_root.name, '/data/' + d['id'], 'RowData'])

                    all_logs.setdefault('All', []).append(logs)
                    if logs_filter_enum:
                        [filter_name, filter_categories, filter_factors], filter_indices, logs_filter = logs_filter_enum
                        for i in range(len(filter_categories)): 
                            if logs_filter[i]:
                                all_logs.setdefault(filter_categories[i].replace('/', '-'), []).append(logs_filter[i])

                zscore_meta_root = meta_root.create_group('zscores')
                zscore_meta_root.attrs.create('customFilterCategory', list(all_logs.keys()))
                zscore_meta_root.attrs.create('customFilterName', filter_name)
                for log_name, log_list in all_logs.items():
                    zscores_2d = [calc_zscore(logs) for logs in log_list]
                    zscores = [np.mean([zscores_2d[j][i] for j in range(len(zscores_2d))]) for i in range(len(zscores_2d[0]))]
                    zscore_meta_root.create_dataset(log_name, data=zscores, compression='gzip', compression_opts=9)

                if (transcript_matrices := d.get('transcript_matrices', None)):
                    transcript_meta_root = meta_root.create_group('transcripts')
                    transcript_meta_root.attrs.create('order', [t['name'] for t in d['transcript_matrices']])
                    for transcript_matrix in d.get('transcript_matrices', []):
                        ranges, categories = transcript_matrix['_internal']
                        curr_transcript_meta_root = transcript_meta_root.create_dataset(transcript_matrix['name'], data=ranges, compression='gzip', compression_opts=9)
                        curr_transcript_meta_root.attrs.create('categories', categories)
                        remote_range_datasets.append([curr_transcript_meta_root.name, '/data/' + d['id'], 'TableData'])

                indices, _, varpart_ranges, varpart_headers = d['_internal']
                reverse_indices = [i for i, x in enumerate(indices) if x != -1]
                meta_root.create_dataset('index', data=reverse_indices, compression='gzip', compression_opts=9)
                
                if varpart_headers:
                    var_ds = meta_root.create_dataset('variance_partition', data=varpart_ranges, compression="gzip", compression_opts=9)
                    var_ds.attrs.create("heading", varpart_headers)

                    remote_range_datasets.append([var_ds.name, '/data/' + d['id'], 'RowData'])

            root.attrs.create('remote', remote_range_datasets)

        # Upload remaining files to release
        asset_paths = [os.path.join(OUTPUT_FOLDER, 'out.hdf5')]
        for d in inputObj['datasets']: 
            m = d['matrices'][0]
            meta_path = os.path.join(d['dir'], d['meta'])
            matrix_path = os.path.join(d['dir'], m['path'])
            matrix_dst = os.path.join(OUTPUT_FOLDER, get_matrix_name(d, m) + '.csv.gz')

            asset_paths.extend([os.path.join(OUTPUT_FOLDER, d['meta']), matrix_dst])
            shutil.copy2(meta_path, OUTPUT_FOLDER)
            os.system(f'gzip -c {matrix_path} > {matrix_dst}')
        
        asset_urls = deploy(asset_paths)

        # Write metadata.csv (TODO: currently only includes first matrix)
        with open(os.path.join(OUTPUT_RESOURCES, 'metadata.json'), 'w') as f:
            meta_json = {
                "data_url": asset_urls.get('out.hdf5', ''),
                "bin_url": expression_url,
                "count": total_written,
                "last_updated": datetime.date.today().strftime("%B %Y"),
                "meta_files": []
            }
            for d in inputObj['datasets']: 
                m = d['matrices'][0]
                meta_json['meta_files'].append({
                    'name': d['id'], 
                    'meta_url': asset_urls.get(d['meta'], ''), 
                    'matrix_url': asset_urls.get(get_matrix_name(d, m) + '.csv.gz', ''),
                    'samples': d['_internal_sample_count']
                })
            json.dump(meta_json, f, indent=2)

if __name__ == '__main__':
    run()