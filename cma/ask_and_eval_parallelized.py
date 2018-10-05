import multiprocessing
import numpy as np
import psutil
import time
from multiprocessing import cpu_count, Process, Queue
import kill_proc_tree
                    
k = 0              
def get_k():
    global k
    x = k
    k += 1
    return x
    
def is_feasible(x, f):
    return not (x is None or f is None or np.isnan(f))

def process_for_ask_and_eval(self, input_queue, output_queue, func, args, length_normalizer, xmean, sigma_fac, evaluations, aggregation, kappa):
    
    
    for x in iter(input_queue.get, 'STOP'):
        
        f = func(x, *args) if kappa == 1 else func(xmean + kappa * length_normalizer * (x - xmean), *args)
        
        if is_feasible(x, f) and evaluations > 1:
            f = aggregation([f] + [(func(x, *args) if kappa == 1 else func(xmean + kappa * length_normalizer * (x - xmean), *args)) for _i in range(int(evaluations - 1))])
            
        output_queue.put((np.asarray(x), f, get_k()))


def ask_and_eval_parallelized(self, func, args, gradf = None, number = None, xmean = None, sigma_fac = 1,
                     evaluations = 1, aggregation = np.median, kappa = 1, number_of_processes = 1):
    
        print("USE ASK_AND_EVAL PARALLELIZED")
        """sample `number` solutions and evaluate them on `func`.

        Each solution ``s`` is resampled until
        ``self.is_feasible(s, func(s)) is True``.

        Arguments
        ---------
        `func`:
            objective function, ``func(x)`` returns a scalar
        `args`:
            additional parameters for `func`
        `gradf`:
            gradient of objective function, ``g = gradf(x, *args)``
            must satisfy ``len(g) == len(x)``
        `number`:
            number of solutions to be sampled, by default
            population size ``popsize`` (AKA lambda)
        `xmean`:
            mean for sampling the solutions, by default ``self.mean``.
        `sigma_fac`:
            multiplier for sampling width, standard deviation, for example
            to get a small perturbation of solution `xmean`
        `evaluations`:
            number of evaluations for each sampled solution
        `aggregation`:
            function that aggregates `evaluations` values to
            as single value.
        `kappa`:
            multiplier used for the evaluation of the solutions, in
            that ``func(m + kappa*(x - m))`` is the f-value for ``x``.

        Return
        ------
        ``(X, fit)``, where

        - `X`: list of solutions
        - `fit`: list of respective function values

        Details
        -------
        While ``not self.is_feasible(x, func(x))`` new solutions are
        sampled. By default ``self.is_feasible == cma.feasible == lambda x, f: f not in (None, np.NaN)``.
        The argument to `func` can be freely modified within `func`.

        Depending on the ``CMA_mirrors`` option, some solutions are not
        sampled independently but as mirrors of other bad solutions. This
        is a simple derandomization that can save 10-30% of the
        evaluations in particular with small populations, for example on
        the cigar function.

        Example
        -------
        >>> import cma
        >>> x0, sigma0 = 8 * [10], 1  # 8-D
        >>> es = cma.CMAEvolutionStrategy(x0, sigma0)  #doctest: +ELLIPSIS
        (5_w,...
        >>> while not es.stop():
        ...     X, fit = es.ask_and_eval(cma.ff.elli)  # handles NaN with resampling
        ...     es.tell(X, fit)  # pass on fitness values
        ...     es.disp(20) # print every 20-th iteration  #doctest: +ELLIPSIS
        Iterat #Fevals...
        >>> print('terminated on ' + str(es.stop()))  #doctest: +ELLIPSIS
        terminated on ...

        A single iteration step can be expressed in one line, such that
        an entire optimization after initialization becomes::

            while not es.stop():
                es.tell(*es.ask_and_eval(cma.ff.elli))

        """
        # initialize
        popsize = self.sp.popsize
        if number is not None:
            popsize = int(number)

        if self.opts['CMA_mirrormethod'] == 1:  # direct selective mirrors
            nmirrors = Mh.sround(self.sp.lam_mirr * popsize / self.sp.popsize)
            self._mirrormethod1_done = self.countiter
        else:
            # method==0 unconditional mirrors are done in ask_geno
            # method==2 delayed selective mirrors are done via injection
            nmirrors = 0
        assert nmirrors <= popsize // 2
        self.mirrors_idx = np.arange(nmirrors)  # might never be used
        is_feasible = self.opts['is_feasible']

        # do the work
        fit = []  # or np.NaN * np.empty(number)
        
        if xmean is None:
            xmean = self.mean  # might have changed in self.ask
        
        X_first = self.ask(number = popsize, xmean = xmean, sigma_fac = sigma_fac, gradf = gradf, args = args)
        
        X = []
        fit = []

        input_queue = Queue()
        output_queue = Queue()

        
        for x in X_first:
            
            #COMMENT : the mirror does NOT work with parallelization since it NEEDS FIT whic is NOT INSTANCIATED
            
            input_queue.put(x.tolist())

        nb_process = min(number_of_processes, cpu_count(), popsize)
        
        length_normalizer = 1

        processes = [Process(name = "Process" + str(i),\
                         target = process_for_ask_and_eval,\
                         args = (self,                            
                                 input_queue,\
                                 output_queue,\
                                 func,\
                                 args,\
                                 length_normalizer,\
                                 xmean,\
                                 sigma_fac,\
                                 evaluations,\
                                 aggregation,\
                                 kappa,)\
                             ) for i in range(nb_process)]

        for process in processes:
            process.start()

        rejected = 0



        rejected = 0
        while len(X) < popsize:

            (x, f, k) = output_queue.get()
            
            if not is_feasible(x, f):
                
                rejected += 1
                
                if (rejected + 1) % 1000 * popsize == 0:
                    print("solutions rejected (f-value NaN or None) at iteration")
                
                new_x = self.ask(number = 1, xmean = xmean, sigma_fac = sigma_fac, gradf = gradf, args = args)[0]
                
                #if k + 1 >= popsize - nmirrors:  # selective mirrors
                    #if k + 1 == popsize - nmirrors:
                        #self.mirrors_idx = np.argsort(fit)[-1:-1 - nmirrors:-1]
                    #new_x = self.get_mirror(X[self.mirrors_idx[popsize - 1 - k]])
                
                input_queue.put(new_x.tolist())
                
            
            else:
                
                X.append(x)
                fit.append(f)

        for process in processes:
                input_queue.put('STOP')

        for process in processes:
            kill_proc_tree.kill_proc_tree(process.pid, include_parent = False, timeout = 0.5, on_terminate = None)

            if process.is_alive():
                process.terminate()
                process.join()

        self.evaluations_per_f_value = int(evaluations)
        if any(f is None or np.isnan(f) for f in fit):
            idxs = [i for i in range(len(fit))
                    if fit[i] is None or np.isnan(fit[i])]
            print("f-values contain None or NaN at indices")
        
        return X, fit
