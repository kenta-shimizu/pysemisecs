

if __name__ == '__main__':
    
    output_files = [
        './simple/secs.py',
        './example/secs.py'
    ]

    target = 'secs'

    files = [
        'secs2body.py',
        'smlparser.py',
        'secsmessage.py',
        'hsmsssmessage.py',
        'secs1message.py',
        'secscommunicator.py',
        'hsmssscommunicator.py',
        'hsmsssactivecommunicator.py',
        'hsmssspassivecommunicator.py',
        'secs1communicator.py',
        'secs1ontcpipcommunicator.py',
        'gem.py'
    ]

    try:
        bf_imports = list()
        bf_lines = list()

        for fn in [('./' + target + '/' + f) for f in files]:

            with open(fn, mode='r') as fp:
                
                print('read file: ' + fn)
                
                for line in [l.rstrip() for l in fp.readlines()]:

                    if line.startswith('import '):
                        s = line[7:].strip()
                        if s != target:
                            bf_imports.append(line)

                    else:
                        bf_lines.append(line)

        targetpath = target + '.'

        for output_file in output_files:

            print('try-write: ' + output_file)

            with open(output_file, mode='w') as fp:

                for line in set(bf_imports):
                    fp.write(line)
                    fp.write('\n')

                for line in bf_lines:
                    s = line.rstrip().replace(targetpath, '')
                    fp.write(s)
                    fp.write('\n')

                fp.write('\n\n')
                fp.write("if __name__ == '__main__':\n")
                fp.write("    print('write here')\n\n")

            print('wrote: ' + output_file)
    
    except Exception as e:
        print(e)
