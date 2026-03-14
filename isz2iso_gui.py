#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
isz2iso_gui – a tiny Tkinter wrapper around the original ISZ→ISO code.
"""
import os
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

# --------------------------------------------------------------
# Put the original conversion classes/functions here.
# --------------------------------------------------------------
import argparse   # we keep only the serialisable parts
import bz2
import ctypes
import zlib

# ---- Original code starts here ----

class ISZ_header(ctypes.LittleEndianStructure):
    _pack_ = 1
    _fields_ = [
        ("signature", ctypes.c_char * 4),
        ("header_size", ctypes.c_ubyte),
        ("version_number", ctypes.c_ubyte),
        ("volume_serial_number", ctypes.c_uint32),
        ("sector_size", ctypes.c_uint16),
        ("total_sectors", ctypes.c_uint),
        ("encryption_type", ctypes.c_ubyte),
        ("segment_size", ctypes.c_int64),
        ("nblock", ctypes.c_uint),
        ("block_size", ctypes.c_uint),
        ("pointer_length", ctypes.c_ubyte),
        ("file_seg_number", ctypes.c_byte),
        ("chunk_pointers_offset", ctypes.c_uint),
        ("segment_pointers_offset", ctypes.c_uint),
        ("data_offset", ctypes.c_uint),
        ("reserved", ctypes.c_ubyte),
        ("checksum1", ctypes.c_uint32),
        ("size1", ctypes.c_uint32),
        ("unknown2", ctypes.c_uint32),
        ("checksum2", ctypes.c_uint32)
    ]

    password_types = {
        0: 'No password',
        1: 'Password protected',
        2: 'Encrypted AES128',
        3: 'Encrypted AES192',
        4: 'Encrypted AES256'
    }

    def read_header(self, f):
        if f.readinto(self) != 64:
            raise Exception('Error while reading the ISZ header only got (%d bytes)' % sys.getsizeof(self))
        if self.signature != b'IsZ!':
            raise Exception('Not an ISZ file (invalid signature)')
        if self.version_number != 1:
            raise Exception('ISZ version not supported')

    def get_uncompressed_size(self):
        return self.sector_size * self.total_sectors

    def get_isz_description(self):
        s = f"ISZ version {self.version_number}, {self.password_types[self.encryption_type]}"
        s += f", volume serial number {hex(self.volume_serial_number)}"
        s += f", uncompressed size={self.get_uncompressed_size() // 1024 // 1024} MB"
        return s

    def print_isz_infos(self):
        print(self.get_isz_description())


class ISZ_sdt(ctypes.LittleEndianStructure):
    _pack_ = 1
    _fields_ = [
        ("size", ctypes.c_int64),
        ("number_of_chunks", ctypes.c_int32),
        ("first_chunck_number", ctypes.c_int32),
        ("chunk_offset", ctypes.c_int32),
        ("left_size", ctypes.c_int32)
    ]


class StorageMethods:
    Zeros, Data, Zlib, Bzip2 = range(4)


class ISZ_File:
    """
    Very small wrapper around the original ISZ file handler.
    """
    def __init__(self):
        self.isz_header = ISZ_header()
        self.isz_segments = []
        self.chunk_pointers = []
        self.fp = None
        self.filename = None

    def close_file(self):
        if self.fp:
            self.fp.close()
            self.fp = None
        self.isz_segments = []
        self.chunk_pointers = []

    def xor_obfuscate(self, data):
        code = (0xb6, 0x8c, 0xa5, 0xde)
        for i in range(len(data)):
            data[i] ^= code[i & 3]
        return data

    def read_chunk_pointers(self):
        if self.isz_header.chunk_pointers_offset == 0:
            self.chunk_pointers.append((1, self.isz_header.size1))
            return
        if self.isz_header.pointer_length != 3:
            raise Exception('Only pointer sizes of 3 implemented')
        size_bytes = self.isz_header.pointer_length * self.isz_header.nblock
        self.fp.seek(self.isz_header.chunk_pointers_offset)
        data = bytearray(self.fp.read(size_bytes))
        data = self.xor_obfuscate(bytearray(data))
        for i in range(self.isz_header.nblock):
            chunk = data[i*3:(i+1)*3]
            val = chunk[2] << 16 | chunk[1] << 8 | chunk[0]
            data_type = val >> 22
            data_size  = val & 0x3fffff
            self.chunk_pointers.append((data_type, data_size))

    def detect_file_naming_convention(self):
        if self.filename.endswith('.isz'):
            for gen in [self.name_generator_1, self.name_generator_2, self.name_generator_3]:
                cand = gen(1)
                if os.path.exists(cand):
                    self.name_generator = gen
                    return
            raise Exception('Unable to find the naming convention used for the multi‑part ISZ file')
        else:
            raise Exception('For multi‑parts ISZ files, the first file need to have an .isz extension')

    def name_generator_1(self, seg_id):
        if seg_id:
            return self.filename[:-4] + f'.i{seg_id:02d}'
        return self.filename

    def name_generator_2(self, seg_id):
        return self.filename[:-11] + f'.part{seg_id+1:02d}.isz'

    def name_generator_3(self, seg_id):
        return self.filename[:-12] + f'.part{seg_id+1:03d}.isz'

    def name_generator_no_change(self, seg_id):
        return self.filename

    def get_segment_name(self, seg_id):
        return self.name_generator(seg_id)

    def check_segment_names(self):
        for i in range(len(self.isz_segments)):
            if not os.path.exists(self.get_segment_name(i)):
                raise Exception(f'Unable to find segment number {i}')

    def read_segment(self):
        data = bytearray(self.fp.read(ctypes.sizeof(ISZ_sdt)))
        data = self.xor_obfuscate(bytearray(data))
        return ISZ_sdt.from_buffer_copy(data)

    def read_segments(self):
        if self.isz_header.segment_pointers_offset == 0:
            seg = ISZ_sdt()
            seg.size = 0
            seg.number_of_chunks = self.isz_header.nblock
            seg.first_chunck_number = 0
            seg.chunk_offset = self.isz_header.data_offset
            seg.left_size = 0
            self.isz_segments.append(seg)
        else:
            self.fp.seek(self.isz_header.segment_pointers_offset)
            seg = self.read_segment()
            while seg.size != 0:
                self.isz_segments.append(seg)
                seg = self.read_segment()
        if len(self.isz_segments) > 1:
            self.detect_file_naming_convention()
        else:
            self.name_generator = self.name_generator_no_change
        self.check_segment_names()

    def open_isz_file(self, filename):
        self.close_file()
        self.filename = filename
        self.fp = open(filename, 'rb')
        self.isz_header.read_header(self.fp)
        if self.isz_header.file_seg_number != 0:
            raise Exception('Not the first segment in a set')
        self.read_segments()
        self.read_chunk_pointers()

    def read_data(self, seg_id, offset, size):
        with open(self.get_segment_name(seg_id), 'rb') as fp:
            fp.seek(offset)
            return fp.read(size)

    def get_block(self, block_id):
        block_type, block_size = self.chunk_pointers[block_id]
        for seg_id, seg in enumerate(self.isz_segments):
            first = seg.first_chunck_number
            last  = seg.first_chunck_number + seg.number_of_chunks - 1
            if first <= block_id <= last:
                cur_offset = seg.chunk_offset
                for i in range(first, block_id):
                    b_type, b_size = self.chunk_pointers[i]
                    if b_type != StorageMethods.Zeros:
                        cur_offset += b_size
                size_to_read = block_size
                if block_id == last and seg.left_size:
                    size_to_read -= seg.left_size
                data = self.read_data(seg_id, cur_offset, size_to_read)
                if block_id == last and seg.left_size:
                    data += self.read_data(seg_id+1, 64, seg.left_size)
                if len(data) != block_size:
                    raise Exception(f'Unable to read block {block_id}')
                return data
        raise Exception(f'Unable to find the segment of block {block_id}')

    def decompress_block(self, block_id):
        typ, size = self.chunk_pointers[block_id]
        if typ == StorageMethods.Zeros:
            return bytes(size)
        data = self.get_block(block_id)
        if typ == StorageMethods.Data:
            return data
        if typ == StorageMethods.Zlib:
            return zlib.decompress(data)
        if typ == StorageMethods.Bzip2:
            data = bytearray(data)
            data[0:3] = b'BZh'          # restore header that was stripped
            return bz2.decompress(data)

    def extract_to(self, dest_iso):
        """Write the decompressed data to <dest_iso>."""
        with open(dest_iso, 'wb') as outf:
            crc = 0
            for block_id in range(len(self.chunk_pointers)):
                data = self.decompress_block(block_id)
                outf.write(data)
                crc = zlib.crc32(data, crc) & 0xffffffff
        # validate
        final = (~crc) & 0xffffffff
        if final != self.isz_header.checksum1:
            raise Exception('CRC Error during extraction')

# ---- Original code ends here ----

# ------------------------------------------------------------------
# GUI application
# ------------------------------------------------------------------
class Application(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("ISZ → ISO converter")
        self.resizable(False, False)
        self.eval("tk::PlaceWindow . center")

        # ------------------------------------------------------------------
        # Variables
        # ------------------------------------------------------------------
        self.src_file  = tk.StringVar()
        self.dest_file = tk.StringVar()

        # ------------------------------------------------------------------
        # Layout
        # ------------------------------------------------------------------
        frm = ttk.Frame(self, padding=(10, 10, 10, 10))
        frm.grid(row=0, column=0, sticky='nsew')
        frm.columnconfigure(1, weight=1)

        # Source – line 0
        ttk.Label(frm, text="Source ISZ file:").grid(row=0, column=0, sticky='w')
        self.src_entry = ttk.Entry(frm, textvariable=self.src_file, width=40)
        self.src_entry.grid(row=0, column=1, sticky='ew', padx=(0, 5))
        self.browse_src_btn = ttk.Button(frm, text='Browse…', command=self.browse_src)
        self.browse_src_btn.grid(row=0, column=2)

        # Destination – line 1
        ttk.Label(frm, text="Destination ISO:").grid(row=1, column=0, sticky='w')
        self.dest_entry = ttk.Entry(frm, textvariable=self.dest_file, width=40)
        self.dest_entry.grid(row=1, column=1, sticky='ew', padx=(0, 5))
        self.browse_dest_btn = ttk.Button(frm, text='Browse…', command=self.browse_dest)
        self.browse_dest_btn.grid(row=1, column=2)

        # Progress bar – line 2
        self.progress_bar = ttk.Progressbar(frm, orient='horizontal',
                                            length=320, mode='determinate')
        self.progress_bar.grid(row=2, columnspan=3, sticky='ew', pady=(5, 0))
        self.progress_bar['maximum'] = 0

        # Status label – line 3
        self.status_lbl = ttk.Label(frm, text='Ready', anchor='center')
        self.status_lbl.grid(row=3, column=0, columnspan=3, pady=(5, 0), sticky='ew')

        # Convert button – line 4
        self.convert_btn = ttk.Button(frm, text='Convert → ISO', command=self.convert)
        self.convert_btn.grid(row=4, column=0, columnspan=3, pady=(10, 0))

    # ------------------------------------------------------------------
    # File selectors
    # ------------------------------------------------------------------
    def browse_src(self):
        path = filedialog.askopenfilename(
            title='Select source ISZ file',
            filetypes=[('ISZ files', '*.isz'), ('All files', '*.*')])
        if path:
            self.src_file.set(path)
            if not self.dest_file.get():
                self.dest_file.set(os.path.splitext(path)[0] + '.iso')

    def browse_dest(self):
        path = filedialog.asksaveasfilename(
            title='Select destination ISO',
            defaultextension='.iso',
            filetypes=[('ISO files', '*.iso'), ('All files', '*.*')])
        if path:
            self.dest_file.set(path)

    # ------------------------------------------------------------------
    # Conversion – runs in a background thread
    # ------------------------------------------------------------------
    def convert(self):
        src = self.src_file.get()
        dest = self.dest_file.get()
        if not src or not os.path.isfile(src):
            messagebox.showerror('Error', 'Please choose a valid .isz file.')
            return
        if not dest:
            messagebox.showerror('Error', 'Please choose a destination file.')
            return

        # Disable UI + initialise UI widgets
        self.disable_ui()
        self.progress_bar['value'] = 0
        self.progress_bar['maximum'] = 0
        self.status_lbl.config(text='Preparing…')

        # Launch worker thread
        threading.Thread(target=self._convert_worker,
                         args=(src, dest), daemon=True).start()

    def _convert_worker(self, src, dest):
        try:
            isz = ISZ_File()
            isz.open_isz_file(src)

            total = len(isz.chunk_pointers)
            # set the maximum once we have the size
            self.after(0, lambda: self.set_progress_max(total))

            # The conversion – write block by block, update progress
            crc = 0
            with open(dest, 'wb') as outf:
                for i in range(total):
                    data = isz.decompress_block(i)
                    outf.write(data)
                    crc = zlib.crc32(data, crc) & 0xffffffff
                    # UI‑safe progress update
                    self.after(0, lambda cur=i+1: self.update_progress(cur))

            isz.close_file()

            # CRC check – identical to the original extract_to()
            if (~crc) & 0xffffffff != isz.isz_header.checksum1:
                raise Exception('CRC error during extraction')

            # Success → re‑enable UI & show a happy dialog
            self.after(0, lambda: self.on_success(dest))
        except Exception as exc:
            # Failure → re‑enable UI & show an error dialog
            self.after(0, lambda: self.on_error(str(exc)))

    # ------------------------------------------------------------------
    # Helper methods that run in the *main* (UI) thread
    # ------------------------------------------------------------------
    def set_progress_max(self, max_value):
        self.progress_bar['maximum'] = max_value
        self.progress_bar['value'] = 0

    def update_progress(self, current):
        self.progress_bar['value'] = current
        max_val = self.progress_bar['maximum']
        self.status_lbl.config(
            text=f'Converting {current}/{max_val} blocks ({current*100//max_val} %)')

    def on_success(self, dest):
        self.enable_ui()
        self.status_lbl.config(text='Done')
        messagebox.showinfo('Success', f'Converted to:\n{dest}')

    def on_error(self, msg):
        self.enable_ui()
        self.status_lbl.config(text='Error')
        messagebox.showerror('Error', msg)

    # ------------------------------------------------------------------
    # UI enable / disable helpers
    # ------------------------------------------------------------------
    def disable_ui(self):
        self.convert_btn['state'] = tk.DISABLED
        self.src_entry['state'] = tk.DISABLED
        self.dest_entry['state'] = tk.DISABLED
        self.browse_src_btn['state'] = tk.DISABLED
        self.browse_dest_btn['state'] = tk.DISABLED

    def enable_ui(self):
        self.convert_btn['state'] = tk.NORMAL
        self.src_entry['state'] = tk.NORMAL
        self.dest_entry['state'] = tk.NORMAL
        self.browse_src_btn['state'] = tk.NORMAL
        self.browse_dest_btn['state'] = tk.NORMAL

# ------------------------------------------------------------------
# Run the application
# ------------------------------------------------------------------
if __name__ == "__main__":
    app = Application()
    app.mainloop()

