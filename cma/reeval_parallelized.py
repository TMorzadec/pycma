"""

In this file I suggest a parallelization of reeval and 'fagg' too.

"""
import psutil
import multiprocessing
from multiprocessing import cpu_count, Process, Queue
import kill_proc_tree

def process_for_fagg(input_queue, output_queue, func, args):
    for x in iter(input_queue.get, 'STOP'):
        
        output_queue.put(func(x, args))


def fagg_parallelized(self, fagg, func, args, X, cpu = 2):
    
    input_queue = Queue()
    output_queue = Queue()

    for x in X:
        input_queue.put(x.tolist())

    nb_process = min(cpu, cpu_count(), len(self.idx))

    processes = [Process(name = "Process" + str(i),\
                         target = process_for_fagg,
                         args = (input_queue, output_queue, func, args)\
                         ) for i in range(nb_process)]


    for process in processes:
        process.start()


    OutPut = []

    while len(OutPut) < len(X):
        
        OutPut.append(output_queue.get())

    for process in processes:
        input_queue.put('STOP')

    for process in processes:
        kill_proc_tree.kill_proc_tree(process.pid, include_parent = False, timeout = 0.5, on_terminate = None)

        if process.is_alive():
            process.terminate()
            process.join()

    return fagg(OutPut)




def process_for_reeval(self, input_queue, output_queue, func, args, ask, fagg, evals):
    
    

    for (i, x) in iter(input_queue.get, 'STOP'):

        if self.epsilon:
            if self.parallel:
                fitre = fagg_parallelized(self, fagg, func, *args, X = ask(evals, x , self.epsilon))
            else:
                
                Y = [ask(1, x, self.epsilon)[0] for _k in range(evals)]
                
                fitre = fagg_parallelized(self, fagg, func, *args, X = Y)
                
        else:
            fitre = fagg_parallelized(self, fagg, func, *args, X = [x for _k in range(evals)])

        output_queue.put((fitre, i))






def reeval_parallelized(self, X, fit, func, ask, args= (), cpu = cpu_count()):
    
    print("USE REEVAL PARALLELIZED")
    
    """store two fitness lists, `fit` and ``fitre`` reevaluating some
    solutions in `X`.
    ``self.evaluations`` evaluations are done for each reevaluated
    fitness value.
    See `__call__`, where `reeval` is called.
    """
    self.fit = list(fit)
    self.fitre = list(fit)
    self.idx = self.indices(fit)
    if not len(self.idx):
        return self.idx

    evals = int(self.evaluations) if self.f_aggregate else 1

    fagg = np.median if self.f_aggregate is None else self.f_aggregate

    input_queue = Queue()
    output_queue = Queue()


    for i in self.idx:
        input_queue.put((i, X[i]))

    nb_process = min(cpu, cpu_count(), len(self.idx))

    processes = [Process(name = "Process" + str(i),\
                         target = process_for_reeval,
                         args = (self, input_queue, output_queue, func, args, ask, fagg, evals, )\
                         ) for i in range(nb_process)]


    for process in processes:
        process.start()


    OutPut = []

    while len(OutPut) < len(self.idx):
        OutPut.append(output_queue.get())

    for process in processes:
        input_queue.put('STOP')

    for process in processes:
        kill_proc_tree.kill_proc_tree(process.pid, include_parent = False, timeout = 0.5, on_terminate = None)

        if process.is_alive():
            process.terminate()
            process.join()

    OutPut.sort()

    for i in self.idx:

        for output in OutPut:
            if output[0] == i:
                self.fitre[i] = output[1]



    return self.fit, self.fitre, self.idx
